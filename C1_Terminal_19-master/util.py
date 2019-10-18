""" Some helper functions. """


def vertical_mirror(points):
    """ Return a list of the mirrored locations of input points. """
    rtn = []
    for point in points:
        rtn.append([27 - point[0], point[1]])
    return rtn
