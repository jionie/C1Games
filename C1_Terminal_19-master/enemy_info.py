from collections import defaultdict, Counter
import gamelib
from util import vertical_mirror

# global constants
LEFT_EDGES = [
    [[13, 27], [12, 26], [11, 25], [10, 24], [9, 23], [8, 22], [7, 21], [6, 20],
     [5, 19], [4, 18], [3, 17], [2, 16], [1, 15], [0, 14]],
    [[13, 26], [12, 25], [11, 24], [10, 23], [9, 22], [8, 21], [7, 20], [6, 19],
     [5, 18], [4, 17], [3, 16], [2, 15], [1, 14]],
    [[13, 25], [12, 24], [11, 23], [10, 22], [9, 21], [8, 20], [7, 19], [6, 18],
     [5, 17], [4, 16], [3, 15], [2, 14]],
    [[13, 24], [12, 23], [11, 22], [10, 21], [9, 20], [8, 19], [7, 18], [6, 17],
     [5, 16], [3, 14]]
]
RIGHT_EDGES = [vertical_mirror(edge) for edge in LEFT_EDGES]
LEFT_CORNER = [[4, 18], [3, 17], [4, 17], [2, 16], [3, 16], [4, 16], [1, 15],
               [2, 15], [3, 15], [4, 15], [0, 14], [1, 14], [2, 14], [3, 14],
               [4, 14]]  # side length = 5
RIGHT_CORNER = [[23, 18], [23, 17], [24, 17], [23, 16], [24, 16], [25, 16],
                [23, 15], [24, 15], [25, 15], [26, 15], [23, 14], [24, 14],
                [25, 14], [26, 14], [27, 14]]  # side length = 5
FRONTIER = [[i, j] for i in range(7, 21) for j in range(14, 19)]


class EnemyState:
    """ Stores information of the opponent. """
    def __init__(self, game_state):
        # gamelib.debug_write("Create Enemy Ojbect!")
        self.game_state = game_state
        # self.defence_units = defaultdict(list)  # TODO: not sure if we need to store all the unit information
        self.defence_locs = defaultdict(list)  # key: type, value: list of locs
        self.scanned = False

    def scan_def_units(self):
        """ Scan the enemy half and store locations of the stationary units. """
        # gamelib.debug_write("...Entering scan_def_units...")
        self.total_units = 0
        for location in self.game_state.game_map:
            if location[1] < 14:  # still in our half
                continue
            for unit in self.game_state.game_map[location]:
                if unit.player_index == 1 and unit.stationary:
                    self.total_units += 1
                    self.defence_locs[unit.unit_type].append(location)
                    # self.defence_units[unit.unit_type].append(unit)
        self.scanned = True
        # gamelib.debug_write("Scan Result:")
        # gamelib.debug_write("{}".format(self.defence_locs))
        # gamelib.debug_write("...Leaving scan_def_units...")

    def detect_def_units(self, target_area=LEFT_CORNER, unit_type=None):
        """
        Return a dictionary {unit_type: # stationary units in target area},
        a count of total units, and a count of total positions.
        If unit type is specified, the dict contains only 1 entry.
        If not, then dict contains info for all defense unit types.
        """
        if not self.scanned:
            self.scan_def_units()
        rtn = {}
        for type, locs in self.defence_locs.items():
            if unit_type != None and unit_type != type:
                continue
            rtn[type] = 0
            for loc in locs:
                if loc in target_area:
                    rtn[type] += 1
        return rtn, sum(rtn.values()), len(target_area)

    def detect_frontier(self, unit_type):
        """
        Return 1) number of total units,
        2) number of total units of given unit_type in frontier,
        3) a tuple (row number with most units, count for this row).
        """
        if not self.scanned:
            self.scan_def_units()
        total_counts = 0
        count = 0
        row_counts = {i:0 for i in range(14, 19)}
        for type, locs in self.defence_locs.items():
            for point in locs:
                if point in FRONTIER:
                    total_counts += 1
                    if type == unit_type:
                        count += 1
                        row_counts[point[1]] += 1
        ctn = Counter(row_counts)
        row_with_most_units = ctn.most_common(1)[0]
        gamelib.debug_write("Total defense units in frontier: {}".format(total_counts))
        gamelib.debug_write("Total {} in frontier: {}".format(unit_type, count))
        gamelib.debug_write("Row {} has most {} ({})".format(row_with_most_units[0], unit_type, row_with_most_units[1]))
        return total_counts, count, row_with_most_units

