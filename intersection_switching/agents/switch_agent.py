import numpy as np
import queue
import operator
from gym import spaces

from agents.agent import Agent

MAXSPEED = 40/3.6 # NOTE: maxspeed is hardcoded
WAIT_THRESHOLD = 120

class SwitchAgent(Agent):
    """
    The class defining an agent which controls the traffic lights using the switching approach
    """
    def __init__(self, env, ID='', in_roads=[], out_roads=[], **kwargs):
        """
        initialises the Analytical Agent
        :param ID: the unique ID of the agent corresponding to the ID of the intersection it represents 
        :param eng: the cityflow simulation engine
        """
        super().__init__(env, ID)

        self.clearing_phase = None
        self.clearing_time = 0

        self.in_roads = in_roads
        self.out_roads = out_roads

        self.action_queue = queue.Queue()
        self.agents_type = 'switch'
        self.approach_lanes = []
        for phase in self.phases.values():
            for movement_id in phase.movements:
                self.approach_lanes += self.movements[movement_id].in_lanes
        self.init_phases_vectors()

        self.n_actions = len(self.phases)
        # nstates = 10
        nstates = len(self.get_vehicle_approach_states({}))
        self.observation_space = spaces.Box(low=np.zeros(self.n_actions+nstates), 
                                            high=np.array([1]*self.n_actions+[100]*nstates),
                                            dtype=float)

        self.action_space = spaces.Discrete(self.n_actions)

    def init_phases_vectors(self):
        """
        initialises vector representation of the phases
        :param eng: the cityflow simulation engine
        """
        idx = 1
        vec = np.zeros(len(self.phases))
        # self.clearing_phase.vector = vec.tolist()
        for phase in self.phases.values():
            vec = np.zeros(len(self.phases))
            if idx != 0:
                vec[idx-1] = 1
            phase.vector = vec.tolist()
            idx += 1

    def observe(self, vehs_distance):
        observations = self.phase.vector + self.get_vehicle_approach_states(vehs_distance)
        return np.array(observations)

    def get_vehicle_approach_states(self, vehs_distance):
        ROADLENGTH = 300 # meters, hardcoded
        VEHLENGTH = 5 # meters, hardcoded

        lane_vehicles = self.env.lane_vehs
        state_vec = []
        for lane_id in self.approach_lanes:
            speeds = []
            waiting_times = []
            for veh_id in lane_vehicles[lane_id]:
                vehicle = self.env.vehicles[veh_id]
                speeds.append(self.env.veh_speeds[veh_id])
                waiting_times.append(vehicle.wait)
            density = len(lane_vehicles[lane_id]) * VEHLENGTH / ROADLENGTH
            ave_speed = np.mean(speeds or 0)
            ave_wait = np.mean(waiting_times or 0)
            # state_vec += [density]
            state_vec += [ave_speed, ave_wait]
            
        density = self.get_in_lanes_veh_num(vehs_distance)
        return state_vec + density
        # return density

    def get_in_lanes_veh_num(self, vehs_distance):
        """
        gets the number of vehicles on the incoming lanes of the intersection
        :param eng: the cityflow simulation engine
        :param lanes_veh: a dictionary with lane ids as keys and list of vehicle ids as values
        :param vehs_distance: dictionary with vehicle ids as keys and their distance on their current lane as value
        """
        ROADLENGTH = 300 # meters, hardcoded
        VEHLENGTH = 5 # meters, hardcoded
        
        lane_vehs = self.env.lane_vehs
        lanes_count = self.env.lanes_count
        lanes_veh_num = []
        for road in self.in_roads:
            lanes = self.env.eng.get_road_lanes(road)
            for lane in lanes:
                seg1 = 0
                seg2 = 0
                seg3 = 0
                vehs = lane_vehs[lane]
                for veh in vehs:
                    if veh in vehs_distance.keys():
                        if vehs_distance[veh] / ROADLENGTH >= (2/3):
                            seg1 += 1
                        elif vehs_distance[veh] / ROADLENGTH >= (1/3):
                            seg2 += 1
                        else:
                            seg3 += 1

                lanes_veh_num.append((seg1 * VEHLENGTH) / (ROADLENGTH/3))
                lanes_veh_num.append((seg2 * VEHLENGTH) / (ROADLENGTH/3))
                lanes_veh_num.append((seg3 * VEHLENGTH) / (ROADLENGTH/3))
        return lanes_veh_num

    
    def aggregate_votes(self, votes, agg_func=None):
        """
        Aggregates votes using the `agg_func`.
        :param votes: list of tuples of (vote, weight). Vote is a boolean to switch phases
        :param agg_func: aggregates votes and weights and returns the winning vote.
        """
        choices = {0: 0, 1: 0}
        if agg_func is None:
            agg_func = lambda x: x
        for vote, weight in votes:
            choices[vote] += agg_func(weight)
        return max(choices, key=choices.get)


    def switch(self, eng, lane_vehs, lanes_count):
        curr_phase = self.phase.ID
        action = abs(curr_phase-1) # ID zero is clearing
        super().apply_action(eng, action, lane_vehs, lanes_count)

    def apply_action(self, eng, phase_id, lane_vehs, lanes_count):
        action = phase_id
        self.update_arr_dep_veh_num(lane_vehs, lanes_count)
        super().apply_action(eng, action, lane_vehs, lanes_count)

    def get_reward(self, type='speed'):
        if type=='speed':
            if self.env.speeds[-self.env.stops_idx:]:
                return np.mean(self.env.speeds[-self.env.stops_idx:])
            else:
                return 0
        if type=='stops':
            return -np.sum(self.env.stops[-self.env.stops_idx:])
        if type=='delay':
            delays = []
            for veh_id, veh_data in self.env.vehicles.items():
                tt = self.env.time - veh_data.start_time
                dist = veh_data.distance
                delay = (tt - dist/MAXSPEED)/dist if dist!= 0 else 0
                delay *= 600 # convert to secs/600m
                delays.append(delay)
            return -np.mean(delays)
        if type=='wait':
            waiting_times = []
            for veh_id in self.env.vehicles.keys():
                vehicle = self.env.vehicles[veh_id]
                waiting_times.append(vehicle.wait)
            if waiting_times:
                return -np.mean(waiting_times)
            else:
                return 0
            
    def calculate_reward(self, lanes_count, type='speed'):

        if type == 'both':
            stops = self.get_reward(type='stops') / (5 * len(self.env.vehicles))
            wait = self.get_reward(type='wait') / 1800

            # reward = stops + wait

            reward = ((-stops)**(0.5) * ((-wait)**(0.5)))
            reward = -1000*reward

            self.total_rewards += [reward]
            self.reward_count += 1
            
            return reward
        else:
            reward = self.get_reward(type=type)
            self.total_rewards += [reward]
            self.reward_count += 1
            return reward

    def rescale_preferences(self, pref, qvals):
        alpha = 0.5
        shift = qvals - qvals.max()
        return np.exp(alpha * shift)/ np.sum(np.exp(alpha*shift))
        # if pref=='speed':
        #     return qvals/(MAXSPEED * 5)
        # elif pref=='wait':
        #     return (np.clip(qvals, -WAIT_THRESHOLD * 5, 0) / (WAIT_THRESHOLD * 5)) + 1
        # elif pref=='stops':
        #     return np.clip(qvals, -len(self.env.vehicles) * 5, 0) / (len(self.env.vehicles) * 5) + 1
