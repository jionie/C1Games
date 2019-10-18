import gamelib
import random
import math
import warnings
from sys import maxsize
import json
import enemy_info
import copy

"""
Most of the algo code you write will be in this file unless you create new
modules yourself. Start by modifying the 'on_turn' function.

Advanced strategy tips:

  - You can analyze action frames by modifying on_action_frame function

  - The GameState.map object can be manually manipulated to create hypothetical
  board states. Though, we recommended making a copy of the map to preserve
  the actual current map state.
"""

class AlgoStrategy(gamelib.AlgoCore):
    def __init__(self):
        super().__init__()
        seed = random.randrange(maxsize)
        random.seed(seed)
        gamelib.debug_write('Random seed: {}'.format(seed))

    def on_game_start(self, config):
        """
        Read in config and perform any initial setup here
        """
        gamelib.debug_write('Configuring your custom algo strategy...')
        self.config = config
        global FILTER, ENCRYPTOR, DESTRUCTOR, PING, EMP, SCRAMBLER
        FILTER = config["unitInformation"][0]["shorthand"]
        ENCRYPTOR = config["unitInformation"][1]["shorthand"]
        DESTRUCTOR = config["unitInformation"][2]["shorthand"]
        PING = config["unitInformation"][3]["shorthand"]
        EMP = config["unitInformation"][4]["shorthand"]
        SCRAMBLER = config["unitInformation"][5]["shorthand"]
        # This is a good place to do initial setup
        self.prev_game_state = None
        self.scored_on_locations = []
        self.has_enemy_left_channal = False
        self.has_enemy_right_channal = False
        self.enemy_state = None
        self.have_middle_attack = False


    def on_turn(self, turn_state):
        """
        This function is called every turn with the game state wrapper as
        an argument. The wrapper stores the state of the arena and has methods
        for querying its state, allocating your current resources as planned
        unit deployments, and transmitting your intended deployments to the
        game engine.
        """
        game_state = gamelib.GameState(self.config, turn_state)
        gamelib.debug_write('Performing turn {} of your custom algo strategy'.format(game_state.turn_number))
        game_state.suppress_warnings(True)  #Comment or remove this line to enable warnings.


        # update enemy_state first
        self.enemy_state = enemy_info.EnemyState(game_state)
        self.enemy_state.scan_def_units()
        self._enemy_channal(self.enemy_state) # check if they have channal

        gamelib.debug_write("@@@@ {0} {1}".format(self.has_enemy_left_channal,self.has_enemy_right_channal))

        self.starter_strategy(game_state)

        self.prev_game_state = copy.deepcopy(game_state)
        game_state.submit_turn()


    """
    NOTE: All the methods after this point are part of the sample starter-algo
    strategy and can safely be replaced for your custom algo.
    """

    def detect_frontier(self, enemy_state, unit_type):
        """
        Return 1) number of total units,
        2) number of total units of given unit_type in frontier,
        3) a tuple (row number with most units, count for this row).
        """
        return enemy_state.detect_frontier(unit_type)

    def _enemy_channal(self,enemy_state):
        gamelib.debug_write("Detecting Enemy states!")
        LEFT_EDGES_2, total_units, totol_positions = enemy_state.detect_def_units(enemy_info.LEFT_EDGES[2])
        if total_units>0.7*totol_positions:
            self.has_enemy_left_channal = True
        else:
            self.has_enemy_left_channal = False


        RIGHT_EDGES_2, total_units, totol_positions = enemy_state.detect_def_units(enemy_info.RIGHT_EDGES[2])
        if total_units>0.7*totol_positions:
            self.has_enemy_right_channal = True
        else:
            self.has_enemy_right_channal = False

    def if_do(self,cut_off=0.5):
        r = random.random()
        return r<cut_off

    def starter_strategy(self, game_state):
        """
        For defense we will use a spread out layout and some Scramblers early on.
        We will place destructors near locations the opponent managed to score on.
        For offense we will use long range EMPs if they place stationary units near the enemy's front.
        If there are no stationary units to attack in the front, we will send Pings to try and score quickly.
        """
        # First, place basic defenses
        self.build_defences(game_state)
        # Now build reactive defenses based on where the enemy scored
        self.build_reactive_defense(game_state)
        # use middle attack
        if game_state.turn_number<3:
            self.middle_attack(game_state)
        else:
            self.main_attack(game_state)
        if self.if_do(1):
            self.edge_attack(game_state)


    def build_defences(self, game_state):
        """
        Build basic defenses using hardcoded locations.
        Remember to defend corners and avoid placing units in the front where enemy EMPs can attack them.
        """
        # Useful tool for setting up your base locations: https://www.kevinbai.design/terminal-map-maker
        # More community tools available at: https://terminal.c1games.com/rules#Download

        # Place destructors that attack enemy units
        # destructor_locations = [[0, 13], [27, 13], [8, 11], [19, 11], [13, 11], [14, 11]]
        destructor_locations = [[7, 10]]+[[2, 12], [25, 12],[26, 12],[1, 12]]
        filters_locations = [[0, 13], [27, 13],[7, 11]] + [[2, 13], [25, 13]]
        encryptors_points = [[2, 11], [25, 11], [3, 10], [24, 10]]
        # attempt_spawn will try to spawn units if we have resources, and will check if a blocking unit is already there
        game_state.attempt_spawn(DESTRUCTOR, destructor_locations)
        game_state.attempt_spawn(ENCRYPTOR, encryptors_points)

        # Place filters in front of destructors to soak up damage for them
        game_state.attempt_spawn(FILTER, filters_locations)
        SCRAMBLER_loc = [[22, 8], [20, 6]] # protect
        if game_state.turn_number<3:
            for loc in SCRAMBLER_loc: # save attack unit
                if self.if_do(0.7):
                    game_state.attempt_spawn(SCRAMBLER, loc,1)
        if self._got_scored_on_corner(left=True):
            self.protect_left_corner(game_state) # check if have attacked

        if self._got_scored_on_corner(left=False):
            self.protect_right_corner(game_state) # check if have attacked


    def build_reactive_defense(self, game_state):
        """
        This function builds reactive defenses based on where the enemy scored on us from.
        We can track where the opponent scored by looking at events in action frames
        as shown in the on_action_frame function
        """
        for location in self.scored_on_locations:
            # Build destructor one space above so that it doesn't block our own edge spawn locations
            build_location = [location[0], location[1]+1]
            game_state.attempt_spawn(DESTRUCTOR, build_location)

    def stall_with_scramblers(self, game_state):
        """
        Send out Scramblers at random locations to defend our base from enemy moving units.
        """
        # We can spawn moving units on our edges so a list of all our edge locations
        friendly_edges = game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_LEFT) + game_state.game_map.get_edge_locations(game_state.game_map.BOTTOM_RIGHT)

        # Remove locations that are blocked by our own firewalls
        # since we can't deploy units there.
        deploy_locations = self.filter_blocked_locations(friendly_edges, game_state)

        # While we have remaining bits to spend lets send out scramblers randomly.
        while game_state.get_resource(game_state.BITS) >= game_state.type_cost(SCRAMBLER) and len(deploy_locations) > 0:
            # Choose a random deploy location.
            deploy_index = random.randint(0, len(deploy_locations) - 1)
            deploy_location = deploy_locations[deploy_index]

            game_state.attempt_spawn(SCRAMBLER, deploy_location)
            """
            We don't have to remove the location since multiple information
            units can occupy the same space.
            """

    def least_damage_spawn_location(self, game_state, location_options):
        """
        This function will help us guess which location is the safest to spawn moving units from.
        It gets the path the unit will take then checks locations on that path to
        estimate the path's damage risk.
        """
        damages = []
        # Get the damage estimate each path will take
        for location in location_options:
            path = game_state.find_path_to_edge(location)
            damage = 0
            for path_location in path:
                # Get number of enemy destructors that can attack the final location and multiply by destructor damage
                damage += len(game_state.get_attackers(path_location, 0)) * gamelib.GameUnit(DESTRUCTOR, game_state.config).damage
            damages.append(damage)

        # Now just return the location that takes the least damage
        return location_options[damages.index(min(damages))]

    def detect_enemy_unit(self, game_state, unit_type=None, valid_x = None, valid_y = None):
        total_units = 0
        for location in game_state.game_map:
            if game_state.contains_stationary_unit(location):
                for unit in game_state.game_map[location]:
                    if unit.player_index == 1 and (unit_type is None or unit.unit_type == unit_type) and (valid_x is None or location[0] in valid_x) and (valid_y is None or location[1] in valid_y):
                        total_units += 1
        return total_units

    def filter_blocked_locations(self, locations, game_state):
        filtered = []
        for location in locations:
            if not game_state.contains_stationary_unit(location):
                filtered.append(location)
        return filtered

    def on_action_frame(self, turn_string):
        """
        This is the action frame of the game. This function could be called
        hundreds of times per turn and could slow the algo down so avoid putting slow code here.
        Processing the action frames is complicated so we only suggest it if you have time and experience.
        Full doc on format of a game frame at: https://docs.c1games.com/json-docs.html
        """
        # Let's record at what position we get scored on
        state = json.loads(turn_string)
        events = state["events"]
        breaches = events["breach"]
        for breach in breaches:
            location = breach[0]
            unit_owner_self = True if breach[4] == 1 else False
            # When parsing the frame data directly,
            # 1 is integer for yourself, 2 is opponent (StarterKit code uses 0, 1 as player_index instead)
            if not unit_owner_self:
                gamelib.debug_write("Got scored on at: {}".format(location))
                self.scored_on_locations.append(location)
                # gamelib.debug_write("All locations: {}".format(self.scored_on_locations))

    def middle_attack(self,game_state):  #Enemy points

        mid_destructors_points_1 = []
        mid_encryptors_points_1 = []
        attack_start = []
        total_count, count, most_row_info = self.detect_frontier(self.enemy_state, DESTRUCTOR)
        if total_count<3:
            return
        row_number,c = most_row_info
        if row_number>16 and total_count<5:
            return
        if row_number==16:
            # check which layer to attack
            attack_start = [22, 8]
            mid_destructors_points_1 = [[12, 13], [17, 13], [21, 12]]
            mid_encryptors_points_1 = [[10, 13], [11, 13], [13, 13], [14, 13], [15, 13], [16, 13], [18, 13], [19, 13], [20, 13], [22, 11],[23,10]]# check if we can build at once
        if row_number==15:
            # check which layer to attack
            attack_start = [21, 7]
            mid_destructors_points_1 = [[12, 12], [15, 12], [18, 12], [21, 11]]
            mid_encryptors_points_1 = [[10, 12], [11, 12], [13, 12], [14, 12], [16, 12], [17, 12], [19, 12], [20, 12], [21, 10], [22, 9]]
        if row_number==14 or count==0:
            # check which layer to attack
            attack_start = [21, 7]
            mid_destructors_points_1 = [[12, 11], [16, 11], [20, 10]]
            mid_encryptors_points_1 = [[10, 11], [11, 11], [13, 11], [14, 11], [15, 11], [17, 11], [18, 11], [19, 11], [21, 9], [22, 8]]
        # check if resource enough
        for loc in mid_destructors_points_1:
            game_state.attempt_spawn(DESTRUCTOR, loc, 1)
        for loc in mid_encryptors_points_1:
            game_state.attempt_spawn(ENCRYPTOR, loc, 1)
        # place unit
        if attack_start==[]:
            return
        self.have_middle_attack = True
        if game_state.turn_number>5:
            if game_state.turn_number%4==0:
                return
            if game_state.turn_number%5==3:
                game_state.attempt_spawn(PING, attack_start, 1000)
        n = random.randint(1,5)
        game_state.attempt_spawn(EMP, attack_start, n) # at least 5

    def _calculate_cores(self, FF, EF, DF):
        filter_cost = self.config["unitInformation"][0]["cost"]
        encryptor_cost = self.config["unitInformation"][1]["cost"]
        destructor_cost = self.config["unitInformation"][2]["shorthand"]
        return FF * filter_cost + EF * encryptor_cost + DF * destructor_cost

    def edge_attack(self,game_state):
        attack_loc = [5,8]
        encryptors_points_1 = [[6, 10], [5, 9], [7, 8], [6, 7], [7, 7]]
        destructors_points_1 = [[5, 10]]
        for loc in destructors_points_1:
            game_state.attempt_spawn(DESTRUCTOR, loc, 1)
        for loc in encryptors_points_1:
            game_state.attempt_spawn(ENCRYPTOR, loc, 1)
        n = random.randint(1,3)
        if game_state.turn_number>12:
            if not game_state.turn_number%6==0:
                return
        if game_state.turn_number>5:
            if game_state.turn_number%4==0:
                n = 1000
        game_state.attempt_spawn(PING, attack_loc, n)


    def protect_left_corner(self,game_state):
        yellow_destructors_points = [[1, 13], [1, 12], [3, 11], [4, 11], [9, 11], [9, 10], [9, 9]]
        yellow_encryptors_points = [[4, 10]]
        yellow_filters_points = [[0, 13], [2, 13], [2, 12], [3, 12], [4, 12], [9, 12], [8, 11], [10, 11]]
        for loc in yellow_destructors_points:
            self.if_do(0.7)
            game_state.attempt_spawn(DESTRUCTOR, loc, 1)
        for loc in yellow_filters_points:
            self.if_do(0.7)
            game_state.attempt_spawn(FILTER, loc, 1)
        for loc in yellow_encryptors_points:
            self.if_do(0.7)
            game_state.attempt_spawn(ENCRYPTOR, loc, 1)

    def protect_right_corner(self,game_state):
        orange_destructors_points = [[24, 13], [25, 13], [24, 12], [25, 12], [26, 12], [23, 11], [24, 11], [25, 11], [23, 10], [23, 9]]
        orange_filters_points = [[23, 13], [26, 13], [23, 12]]
        # orange_destructors_points = [[24, 12], [25, 12], [24, 11]]
        # orange_filters_points = [[24, 13], [25, 13], [26, 13]]
        for loc in orange_destructors_points:
            self.if_do(0.7)
            game_state.attempt_spawn(DESTRUCTOR, loc, 1)
        for loc in orange_filters_points:
            self.if_do(0.7)
            game_state.attempt_spawn(FILTER, loc, 1)


    def _got_scored_on_corner(self, left=True):
        if left:
            targets = [[0, 13], [1, 12], [2, 11], [3, 10], [4, 9]]
        else:
            targets = [[27, 13], [26, 12], [25, 11], [24, 10], [23, 9]]
        for point in self.scored_on_locations:
            if point in targets:
                return True
        return False

    def main_attack(self,game_state):
        if self.have_middle_attack:
            return
        purple_destructors_points = [[11, 6], [13, 6], [16, 6], [18, 6]]
        purple_encryptors_points = [[11, 5], [13, 5], [14, 5], [15, 5], [16, 5], [17, 5], [18, 5], [19, 5], [11, 4], [10, 3], [12, 3], [13, 3], [14, 3], [15, 3], [13, 2], [14, 2]]
        purple_filters_points = [[11, 7], [13, 7], [16, 7], [18, 7]]
        attack_start_1 = [11,2]
        attack_start_2 = [15,1]
        self.use_main_attack=1
        for idx in range(len(purple_destructors_points)):
            if self.if_do(0.3):
                game_state.attempt_spawn(FILTER, purple_filters_points[idx], 1)
                game_state.attempt_spawn(DESTRUCTOR, purple_destructors_points[idx], 1)
        for loc in purple_encryptors_points:
            game_state.attempt_spawn(ENCRYPTOR, loc, 1)

        best_location = self.least_damage_spawn_location(game_state, [attack_start_1,attack_start_2])
        # if self.if_do(0.5):
        #     best_location = attack_start_1
        # else:
        #     best_location = attack_start_2
        if game_state.turn_number>12:
            if not game_state.turn_number%4==0:
                return
        game_state.attempt_spawn(PING, best_location, 1000)



if __name__ == "__main__":
    algo = AlgoStrategy()
    algo.start()
