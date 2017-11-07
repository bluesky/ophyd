from ophyd.sim import SynGauss, Syn2DGauss, SynAxis
import numpy as np


def test_random_state_gauss1d():
    """With given random state, the output value should stay the same.
    Test performs on 1D gaussian.
    """
    dlist=  []
    motor = SynAxis(name='motor')
    for i in range(2):
        s = np.random.RandomState(0)
        noisy_det = SynGauss('noisy_det', motor, 'motor', center=0, Imax=1,
                             noise='uniform', sigma=1, noise_multiplier=0.1,
                             random_state=s)
        noisy_det.trigger()
        d = noisy_det.read()['noisy_det']['value']
        dlist.append(d)
    assert dlist[0] == dlist[1]


def test_random_state_gauss2d():
    """With given random state, the output value should stay the same.
    Test performs on 2D gaussian.
    """
    dlist=  []
    motor1 = SynAxis(name='motor1')
    motor2 = SynAxis(name='motor2')
    for i in range(2):
        s = np.random.RandomState(0)
        noisy_det = Syn2DGauss('noisy_det', motor1, 'motor1', motor2, 'motor2',
                                center=(0, 0), Imax=1, noise='uniform',
                                sigma=1, noise_multiplier=0.1, random_state=s)
        noisy_det.trigger()
        d = noisy_det.read()['noisy_det']['value']
        dlist.append(d)
    assert dlist[0] == dlist[1]
