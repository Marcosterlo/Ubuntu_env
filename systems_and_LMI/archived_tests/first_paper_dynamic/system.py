import numpy as np
import scipy.io
import torch
import torch.nn as nn
import matplotlib.pyplot as plt
from scipy.linalg import block_diag
import os

class System:
  
  def __init__(self):
    
    ## Parameters
    self.g = 9.81 # Gravity coefficient
    self.m = 0.15 # mass
    self.l = 0.5 # length
    self.mu = 0.05 # frict coeff
    self.dt = 0.02 # sampling period

    ## System definition x^+ = A*x + B*u

    self.A = np.array([[1,      self.dt],
                  [self.g/self.l*self.dt, 1 - self.mu/(self.m*self.l**2)*self.dt]])

    self.B = np.array([[0],
                  [self.dt/(self.m*self.l**2)]])

    # Size of vector x
    self.nx = 2

    # Size of input u
    self.nu = 1

    # Weights import of trained FFNN
    # Script to use relative path
    mat_name = os.path.abspath(__file__ + "/../mat-weights/weight_saturation.mat")
    data = scipy.io.loadmat(mat_name)
    W1 = data['W1']
    W2 = data['W2']
    W3 = data['W3']

    # Vector of weigts
    self.W = [W1, W2, W3]

    # Number of neurons
    self.nphi = W1.shape[0] + W2.shape[0]
    
    # Bias import of trained FFNN
    b1 = data['b1']
    b2 = data['b2']
    b3 = data['b3']
    b1 = b1.reshape(len(b1))
    b2 = b2.reshape(len(b2))
    b3 = b3.reshape(len(b3))

    # Vector of biases
    self.b = [b1, b2, b3]

    # Neurons per layer in the FFNN (to substitute with array if different)
    neurons = 32*np.ones((1,2)).astype(np.int16)
    self.neurons = neurons.tolist()[0]

    # Closed loop matrices
    N = block_diag(*self.W) # Reminder for myself: * operator unpacks lists and pass it as singular arguments
    Nux = N[self.nphi:, :self.nx]
    Nuw = N[self.nphi:, self.nx:]
    Nub = self.b[-1]
    Nvx = N[:self.nphi, :self.nx]
    Nvw = N[:self.nphi, self.nx:]
    Nvb = np.concatenate((self.b[0], self.b[1]))

    # Auxiliary matrices
    R = np.linalg.inv(np.eye(*Nvw.shape) - Nvw)
    Rw = Nux + Nuw @ R @ Nvx
    Rb = Nuw @ R @ Nvb + Nub

    # Equilibrium states
    self.xstar = np.linalg.inv(np.eye(self.A.shape[0]) - self.A - self.B @ Rw) @ self.B @ Rb
    wstar = R @ Nvx @ self.xstar + R @ Nvb

    # I create the array indeces to split wstar into
    indeces = [self.neurons[0]]
    self.wstar = np.split(wstar, indeces)

    # Number of layers of the FFNN (+1 to include last layer for input computation)
    self.nlayer = 3

    # Bound value for saturation function
    self.bound = 1

    # Model creation
    self.layer1 = nn.Linear(self.nx, W1.shape[0])
    self.layer2 = nn.Linear(W1.shape[0], W2.shape[0])
    self.layer3 = nn.Linear(W2.shape[0], self.nu)

    # Weights import
    self.layer1.weight = nn.Parameter(torch.tensor(W1))
    self.layer2.weight = nn.Parameter(torch.tensor(W2))
    self.layer3.weight = nn.Parameter(torch.tensor(W3))

    self.layer1.bias = nn.Parameter(torch.tensor(b1))
    self.layer2.bias = nn.Parameter(torch.tensor(b2))
    self.layer3.bias = nn.Parameter(torch.tensor(b3))

    self.layers = [self.layer1, self.layer2, self.layer3]

    # Qw and Qdelta matrices import from LMI solution with relative path
    Qw_mat_name = os.path.abspath(__file__ + "/../mat-weights/Qw_mat.npy")
    Qdelta_mat_name = os.path.abspath(__file__ + "/../mat-weights/Qdelta_mat.npy")
    Qw_tot = np.load(Qw_mat_name)
    Qdelta_tot = np.load(Qdelta_mat_name)
    self.Qw = []
    self.Qdelta = []
    for i in range(self.nlayer - 1):
      self.Qw.append(Qw_tot[i*self.neurons[i]:(i+1)*self.neurons[i], i*self.neurons[i]:(i+1)*self.neurons[i]])
      self.Qdelta.append(Qdelta_tot[i*self.neurons[i]:(i+1)*self.neurons[i], i*self.neurons[i]:(i+1)*self.neurons[i]])


    ## Class variable
    self.state = None
    self.last_w = []
    for i, neuron in enumerate(self.neurons):
      # Initialized with big values to trigger an update at first time step
      self.last_w.append(np.ones((neuron, 1))*1e3)
      # Reshape of wstar vector to make it compatible with last_w
      self.wstar[i] = self.wstar[i].reshape(len(self.wstar[i]), 1)
  
    self.eta = 1
    self.rho = 0.1
    self.lam = 0.1

  ## Function that predicts the input
  def forward(self, x, ETM):

    val = 0
    
    # Reshape fo state according to NN dimensions
    x = x.reshape(1, self.W[0].shape[1])
    
    # Initialization of empty vector to store events
    e = np.zeros(self.nlayer - 1)

    break_cascade = False

    # Loop for each layer
    for l in range(self.nlayer - 1):
      if not break_cascade: 
        # If we are in the fist layer the input is initial x, otherwise it is the omega of the previous layer
        if l == 0:
          # Detach, numpy and reshape are used to cast to np array of the correct shape in order to hav
          nu = self.layers[l](torch.tensor(x)).detach().numpy().reshape(self.W[l].shape[0], 1)
        else:
          nu = self.layers[l](torch.tensor(omega.reshape(1, self.W[l].shape[1]))).detach().numpy().reshape(self.W[l].shape[0], 1)

        omega = self.saturation_activation(torch.tensor(nu)).detach().numpy().reshape(self.W[l].shape[0], 1)

        # ETM evaluation
        vec1 = self.last_w[l] - omega
        vec2 = omega - self.wstar[l]

        # Flag to enbale/disable ETM
        if ETM:
          check = vec1.T @ self.Qdelta[l] @ vec1 - vec2.T @ self.Qw[l] @ vec2 > self.rho * self.eta 
        else:
          check = True

        if check:
          self.last_w[l] = omega
          e[l] = 1
          val += (- vec2.T @ self.Qw[l] @ vec2)[0][0]
        else:
          val += (vec1.T @ self.Qdelta[l] @ vec1 - vec2.T @ self.Qw[l] @ vec2)[0][0]
          # If no event occurs we feed the next layer the last stored output
          break_cascade = True
          omega = self.last_w[l]

    # Last layer, different since it doesn't need ETM evaluation and w value update
    l = self.nlayer - 1
    if break_cascade:
      omega = self.last_w[-1]
    nu = self.layers[l](torch.tensor(omega.reshape(1, self.W[l].shape[1])))
    omega = nu.detach().numpy().reshape(self.W[l].shape[0], 1)

    self.eta = (self.rho + self.lam) * self.eta - val

    return omega, e, self.eta

  ## Customly defined activation function since sat doesn't exist on tensorflow
  def saturation_activation(self, value):
    return torch.clamp(value, min=-self.bound, max=self.bound)

  ## Function that evaluates the closed loop dynamics
  def dynamic_loop(self, x0, nstep, ETM):

    # Initializes the state variable of the system to the initial condition
    if self.state == None:
      self.state = x0

    states = []
    inputs = []
    events = []
    etas = []

    # Loop called at each step
    for i in range(nstep):

      # Input computation via NN controller, events are tracked
      u, e, eta = self.forward(self.state, ETM)
      
      # Forward dynamics
      x = self.A  @ self.state.reshape(2,1) + self.B @ u.reshape(1, 1)

      # Optional noise addition
      # self.state = x + (np.random.randn(self.nx)*self.stdx).reshape(2, 1)
      self.state = x
      # u = u + np.random.randn(self.nu)*self.stdu

      states.append(x)
      inputs.append(u)
      events.append(e)
      etas.append(eta)

    return np.array(states), np.array(inputs), np.array(events), np.array(etas)
  

# Main execution
if __name__ == "__main__":

  # Systam object creation
  s = System()

  # Import of P matrix from LMI solution
  P_mat_name = os.path.abspath(__file__ + "/../mat-weights/P_mat.npy")
  P = np.load(P_mat_name)
  
  # Empty vectors initialization
  states = []
  inputs = []
  events = []
  etas = []
  lyap = []

  # Simulation parameters
  x0 = np.array([np.pi*3/8, -5])
  # In time it's nstep*s.dt = nstep * 0.02 s
  nstep = 500
  ETM = True
  print_events = True

  # Call to simulation function of object System
  states, inputs, events, etas = s.dynamic_loop(x0, nstep, ETM)

  layer1_trigger = np.sum(events[:, 0]) / nstep * 100
  layer2_trigger = np.sum(events[:, 1]) / nstep * 100

  print("Layer 1 has been triggered " + str(layer1_trigger) + "% of times")
  print("Layer 2 has been triggered " + str(layer2_trigger) + "% of times")
  
  # Unpacking vectors
  x = states[:, 0]
  v = states[:, 1]
  u = inputs.reshape(len(inputs))
  time_grid = np.linspace(0, nstep * s.dt, nstep)
  
  # Creation of lyapunov function vector
  for i in range(nstep):
    lyap.append(((states[i, :] - s.xstar).T @ P @ (states[i, :] - s.xstar))[0][0])

  # Conversion of non events to None for ease of plotting
  for i, event in enumerate(events):
    if not event[0]:
      events[i][0] = None
    if not event[1]:
      events[i][1] = None

  ## Plotting
  
  fig, axs = plt.subplots(2, 2)
  axs[0, 0].plot(time_grid, x - s.xstar[0])
  if print_events:
    axs[0, 0].plot(time_grid, events[:, 1]*(x - s.xstar[0]).reshape(len(time_grid)), 'ro')
  axs[0, 0].set_title("Position")
  axs[0, 0].set_xlabel("Time [s]")
  axs[0, 0].set_ylabel("Position [rad]")

  axs[0, 1].plot(time_grid, v - s.xstar[1])
  if print_events:
    axs[0, 1].plot(time_grid, events[:, 1]*(v - s.xstar[1]).reshape(len(time_grid)), 'ro')
  axs[0, 1].set_title("Velocity")
  axs[0, 1].set_xlabel("Time [s]")
  axs[0, 1].set_ylabel("Velocity [rad/s]")

  axs[1, 0].plot(time_grid, u)
  if print_events:
    axs[1, 0].plot(time_grid, events[:, 1]*u, 'ro')
  axs[1, 0].set_title("Inputs")
  axs[1, 0].set_xlabel("Time [s]")
  axs[1, 0].set_ylabel("Control input")

  if print_events:
    axs[1, 1].plot(time_grid, events[:, 1]*lyap, 'ro')
  axs[1, 1].plot(time_grid, lyap)
  axs[1, 1].set_title("Lyapunov function")

  plt.show()

  x1_vals = []
  x2_vals = []
  P0 = np.array([[0.3024, 0.0122], [0.0122, 0.0154]])
  x11_vals = []
  x21_vals = []

  for i in range(100000):
    x1 = np.random.uniform(-10, 10) - s.xstar[0]
    x2 = np.random.uniform(-20, 20) - s.xstar[1]
    vec = np.array([x1, x2])
    if (vec.T @ P @ vec < 1):
      x1_vals.append(x1)
      x2_vals.append(x2)
    if (vec.T @ P0 @ vec < 1):
      x11_vals.append(x1)
      x21_vals.append(x2)

  plt.plot(x1_vals, x2_vals, marker='o')
  plt.plot(x11_vals, x21_vals, marker='o')
  plt.plot(x, v)
  plt.xlabel('x1')
  plt.ylabel('x2')
  plt.title('ROA')
  plt.grid(True)
  plt.legend()
  plt.show()