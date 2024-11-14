from systems_and_LMI.systems.NonLinPendulum_kETM_train import NonLinPendulum_kETM_train
import os
import numpy as np
import matplotlib.pyplot as plt

W1_name = os.path.abspath(__file__ + "/../new_weights/mlp_extractor.policy_net.0.weight.csv")
W2_name = os.path.abspath(__file__ + "/../new_weights/mlp_extractor.policy_net.2.weight.csv")
W3_name = os.path.abspath(__file__ + "/../new_weights/mlp_extractor.policy_net.4.weight.csv")
W4_name = os.path.abspath(__file__ + "/../new_weights/action_net.weight.csv")

b1_name = os.path.abspath(__file__ + "/../new_weights/mlp_extractor.policy_net.0.bias.csv")
b2_name = os.path.abspath(__file__ + "/../new_weights/mlp_extractor.policy_net.2.bias.csv")
b3_name = os.path.abspath(__file__ + "/../new_weights/mlp_extractor.policy_net.4.bias.csv")
b4_name = os.path.abspath(__file__ + "/../new_weights/action_net.bias.csv")

W1 = np.loadtxt(W1_name, delimiter=',')
W2 = np.loadtxt(W2_name, delimiter=',')
W3 = np.loadtxt(W3_name, delimiter=',')
W4 = np.loadtxt(W4_name, delimiter=',')
W4 = W4.reshape((1, len(W4)))

W = [W1, W2, W3, W4]

b1 = np.loadtxt(b1_name, delimiter=',')
b2 = np.loadtxt(b2_name, delimiter=',')
b3 = np.loadtxt(b3_name, delimiter=',')
b4 = np.loadtxt(b4_name, delimiter=',')

b = [b1, b2, b3, b4]

s = NonLinPendulum_kETM_train(W, b, 0.0)

P = np.load('ETM/P.npy')

in_ellip = False
while not in_ellip:
  theta = np.random.uniform(-np.pi/2, np.pi/2)
  vtheta = np.random.uniform(-s.max_speed, s.max_speed)
  ref = np.random.uniform(-0.5, 0.5)
  s = NonLinPendulum_kETM_train(W, b, ref)
  x0 = np.array([[theta], [vtheta], [0.0]])
  if (x0 - s.xstar).T @ P @ (x0 - s.xstar) <= 1:
      in_ellip = True
      print(f"Initial state: theta0 = {theta*180/np.pi:.2f} deg, vtheta0 = {vtheta:.2f} rad/s, constant reference = {ref*180/np.pi:.2f} deg")
      s.state = x0
  
nsteps = 300

states = []
inputs = []
events = []
etas = []
lyap = []

for i in range(nsteps):
  state, u, e, eta = s.step()
  states.append(state)
  inputs.append(u)
  events.append(e)
  etas.append(eta)
  lyap.append((state - s.xstar).T @ P @ (state - s.xstar) + 2*eta[0] + 2*eta[1] + 2*eta[2])

states = np.squeeze(np.array(states))
inputs = np.squeeze(np.array(inputs))
events = np.squeeze(np.array(events))
etas = np.squeeze(np.array(etas))
lyap = np.squeeze(np.array(lyap))

timegrid = np.arange(0, nsteps)

layer1_trigger = np.sum(events[:, 0]) / nsteps * 100
layer2_trigger = np.sum(events[:, 1]) / nsteps * 100
layer3_trigger = np.sum(events[:, 2]) / nsteps * 100

print(f"Layer 1 has been triggered {layer1_trigger:.1f}% of times")
print(f"Layer 2 has been triggered {layer2_trigger:.1f}% of times")
print(f"Layer 3 has been triggered {layer3_trigger:.1f}% of times")

for i, event in enumerate(events):
  if not event[0]:
    events[i][0] = None
  if not event[1]:
    events[i][1] = None
  if not event[2]:
    events[i][2] = None
    
fig, axs = plt.subplots(4, 1)
axs[0].plot(timegrid, inputs, label='Control input')
axs[0].plot(timegrid, inputs * events[:, 2], marker='o', markerfacecolor='none')
axs[0].set_xlabel('Time steps')
axs[0].set_ylabel('Values')
axs[0].legend()
axs[0].grid(True)

axs[1].plot(timegrid, states[:, 0], label='Position')
axs[1].plot(timegrid, timegrid * 0 + s.xstar[0], 'r--')
axs[1].plot(timegrid, states[:, 0] * events[:, 2], marker='o', markerfacecolor='none')
axs[1].set_xlabel('Time steps')
axs[1].set_ylabel('Values')
axs[1].legend()
axs[1].grid(True)

axs[2].plot(timegrid, states[:, 1], label='Velocity')
axs[2].plot(timegrid, states[:, 1] * events[:, 2], marker='o', markerfacecolor='none')
axs[2].plot(timegrid, timegrid * 0 + s.xstar[1], 'r--')
axs[2].set_xlabel('Time steps')
axs[2].set_ylabel('Values')
axs[2].legend()
axs[2].grid(True)

axs[3].plot(timegrid, states[:, 2], label='Integrator state')
axs[3].plot(timegrid, states[:, 2] * events[:, 2], marker='o', markerfacecolor='none')
axs[3].plot(timegrid, timegrid * 0 + s.xstar[2], 'r--')
axs[3].set_xlabel('Time steps')
axs[3].set_ylabel('Values')
axs[3].legend()
axs[3].grid(True)
plt.show()

plt.plot(timegrid, etas[:, 0], label='Eta_1')
plt.plot(timegrid, etas[:, 1], label='Eta_2')
plt.plot(timegrid, etas[:, 2], label='Eta_3')
plt.legend()
plt.grid(True)
plt.show()

plt.plot(timegrid, lyap, label='Lyapunov function')
plt.legend()
plt.grid(True)
plt.show()