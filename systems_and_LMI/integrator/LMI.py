import cvxpy as cp
import numpy as np
from system import Integrator

s = Integrator()

# Values import
A = s.A
B = s.B
R = s.R
Rw = s.Rw
Rb = s.Rb
N = s.N
Nux = N[0]
Nuw = N[1]
Nub = N[2]
Nvx = N[3]
Nvw = N[4]
Nvb = N[5]
nphi = s.nphi
nx = s.nx
nu = s.nu
neurons = [32, 32, 32]
g = s.g
l = s.l
dt = s.dt
nlayer = s.nlayer

# Variables
Ptrue = cp.Variable((nx, nx), symmetric=True)
transf = cp.bmat([
    [1, 0, 0],
    [0, 1, 0],
    [0, 0, 0]
])
P_ellip =  transf @ Ptrue @ transf
T_val = cp.Variable(nphi)
T = cp.diag(T_val)
Z1 = cp.Variable((neurons[0], nx))
Z2 = cp.Variable((neurons[1], nx))
Z3 = cp.Variable((neurons[2], nx))
Z = cp.vstack([Z1, Z2, Z3])

# Composite matrices
Abar = A + B @ Rw

mat1 = cp.bmat([
  [np.zeros((nx, nx)), np.zeros((nx, nphi)), np.zeros((nx, nphi))],
  [Z, -T, T],
  [np.zeros((1, nx)), np.zeros((1, nphi)), np.zeros((1, nphi))]
])

Rphi = cp.bmat([
  [np.eye(nx), np.zeros((nx, nphi)), np.zeros((nx, 1))],
  [R @ Nvx, np.eye(R.shape[0]) - R, np.zeros((nphi, 1))],
  [np.zeros((nphi, nx)), np.eye(nphi), np.zeros((nphi, 1))]
])

Rq = cp.bmat([
  [np.hstack([1, 0, 0, np.zeros(nphi), 0]).reshape(1, nx + nphi + 1)],
  [np.hstack([0, 0, 0, np.zeros(nphi), 1]).reshape(1, nx + nphi + 1)]
])

sec_mat = cp.bmat([
  [0, -1],
  [-1, -2]
])

P_mat = cp.bmat([
  [Ptrue, np.zeros((nx, nphi)), np.zeros((nx, 1))],
  [np.zeros((nphi, nx)), np.zeros((nphi, nphi)), np.zeros((nphi, 1))],
  [np.hstack([np.zeros(nx), np.zeros(nphi), 0]).reshape(1, nx + nphi + 1)]
])

q = np.array([[0],
             [g/l*dt],
             [0]]) 

global_sec_factor = cp.Variable()

M = cp.vstack([Abar.T, (-B @ Nuw @ R).T, q.T]) @ Ptrue @ cp.hstack([Abar, -B @ Nuw @ R, q])- P_mat - Rphi.T @ mat1.T - mat1 @ Rphi -global_sec_factor * Rq.T @ sec_mat @ Rq

## Constraints
constraints = [Ptrue >> 0]
constraints += [T >> 0]
constraints += [M << 0]
constraints += [global_sec_factor >= 0]

vbar = 1
alpha = 9 * 1e-4

# Ellipsoid condition
for i in range(nlayer-1):
    for k in range(neurons[i]):
        Z_el = Z[i*neurons[i] + k]
        T_el = T[i*neurons[i] + k, i*neurons[i] + k]
        vcap = np.min([np.abs(-vbar -s.wstar[i][k][0]), np.abs(vbar - s.wstar[i][k][0])], axis=0)
        ellip = cp.bmat([
            [P_ellip, cp.reshape(Z_el, (3,1))],
            [cp.reshape(Z_el, (1,3)), cp.reshape(2*alpha*T_el - alpha**2*vcap**(-2), (1, 1))] 
        ])
        constraints += [ellip >> 0]

objective = cp.Minimize(cp.trace(Ptrue))
prob = cp.Problem(objective, constraints)

prob.solve(solver=cp.MOSEK, verbose=True)
if prob.status not in  ["infeasible", "ubounded", "unbounded_inaccurate", "infeasible_inaccurate"]:
  print(f"\n\n++++++++++++++++++++++++++++++++++++++++++++++\n                  LMI SOLVED\n++++++++++++++++++++++++++++++++++++++++++++++\n\n")
  print("Problem status is " + prob.status)
  print("Max P eigenvalue: ", np.max(np.linalg.eigvals(Ptrue.value)))
  print("Max M eigenvalue: ", np.max(np.linalg.eigvals(M.value)))
  print("Max T eigenvalue: ", np.max(np.linalg.eigvals(T.value)))
else:
  print(f"Mosek failed")