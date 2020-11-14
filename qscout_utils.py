import numpy as np

DIRECTION_RIGHT = 0
DIRECTION_UP = 1
DIRECTION_LEFT = 2
DIRECTION_DOWN = 3
NUM_DIRECTIONS = 4
DIRECTIONS = (
    (1, 0),
    (0, 1),
    (-1, 0),
    (0, -1)
)


def calc_margins(sample1, sample2):
    """
    given two Sample objects of different shapes, calculates the margins to apply to each one
    to give to matrices of the same shape and the same area
    """
    return as_margins(np.maximum(sample2.offsets - sample1.offsets, np.zeros(shape=[NUM_DIRECTIONS], dtype=np.int16))),\
           as_margins(np.maximum(sample1.offsets - sample2.offsets, np.zeros(shape=[NUM_DIRECTIONS], dtype=np.int16)))


def as_margins(m):
    return np.s_[
            m[DIRECTION_LEFT]:-m[DIRECTION_RIGHT] if m[DIRECTION_RIGHT] > 0 else None,
            m[DIRECTION_DOWN]:-m[DIRECTION_UP] if m[DIRECTION_UP] > 0 else None,
    :]


def gradient(a):
    '''
    @param a:  a matrix of (n x p x q), where n and p are the width and height. r will be essentially ignored
    @return an array of shape (n - 2r, p - 2r, q, 2) of x and y magnitudes of the gradient vectors. [:,:,:,0] is x
        magnitudes, [:,:,:,1] is y-magniutes. algorithm is incomplete; only does partial use of non-row and column
        differences. this is a deliberate choice for computational power reasons
    '''
    r = 2
    d = 2*r+1
    w = a.shape[0]
    h = a.shape[1]
    vectors = np.zeros((w - 2*r, h - 2*r, a.shape[2], d, d))
    base = a[r:-r, r:-r, :]
    for x in range(d):
        for y in range(d):
            shift_x = x - (r + 1)
            shift_y = y - (r + 1)
            if shift_x == 0 and shift_y == 0:
                # trying to take gradient from (0,0) rel position
                continue
            shift = a[x:x + (w - 2*r), y: y + (h - 2*r), :]
            vectors[..., x, y] = (base - shift) / (math.pow(shift_x, 2) + math.pow(shift_y, 2))
    x_grad = np.sum(vectors, axis=3)[:, :, :, r + 1]
    y_grad = np.sum(vectors, axis=4)[:, :, :, r + 1]

    return np.stack((x_grad, y_grad), axis=-1)


def reverse_direction(direction):
    return int((direction + (NUM_DIRECTIONS / 2)) % NUM_DIRECTIONS)
