# -*- coding: utf-8 -*-
from truck_methods import Truck
import numpy as np
from datetime import datetime, timedelta
import random
import networkx as nx
import math
class Carrier:

    def __init__(
            self,
            carrier_index:int,
            carrier_size_type:int,
            public_prime:int
            ) -> None:
        
        self.truck_index_list   = []
        self.carrier_index      = carrier_index
        self.carrier_size_type  = carrier_size_type # Not in used for now
        self.truck_list         = []

        self.current_slot_com       = 0
        self.is_in_communication    = False
        self.public_prime           = public_prime
        self.carrier_qty_est        = 1

        self.enc_data_table_base = datetime(2000,1,1,0,0,0,0)

        self.neighoring_carrier_index = []
        # self.encrypted_data
        # self.secret_part_kept       = np.array()

        # with all trucks in the list, it should be able to generate the matrix for transmitting
        # self.next_period_plan_matrix = np.array()

        # self.next_period_plan_matrix_memory = self.next_period_plan_matrix

        self.enc_service_flag = False

    def add_truck_into_this_carrier(self,truck2add:Truck) -> None:
        self.truck_list.append(truck2add)
        self.truck_index_list.append(truck2add.truck_index)

    def get_my_neighbor_carrier(self,data:dict) -> None:
        for _truck in self.truck_list:
            conn_truck_list = data[_truck.current_node]
            for _truck_index in conn_truck_list:
                if _truck_index == _truck.truck_index:
                    continue
                # how do I know who is there?

    def space_time_plan_table_init(self,edge_list:list,future_range:int,time_resolution:int) -> np.array:
        # all unit given in minute
        # it presented if the truck leaves in [left,right)
        # therefore, if we look forward 1 hour, and we need to know the depature trucks per minute
        # future_range = 60, time_resolution = 1

        # record these information
        self.future_range       = future_range
        self.time_resolution    = time_resolution
        # build empty matrix
        n_of_rows = int(future_range/time_resolution)
        n_of_cols = len(edge_list)
        return np.zeros((n_of_rows, n_of_cols))
    
    def load_truck_plan_into_table(self,base_line_clk:datetime) -> None:
        _temp = np.zeros(self.next_period_plan_matrix.shape)
        for _truck in self.truck_list:
            _this_truck_departure_time = _truck.generate_depature_time_list()
            for _relative_node_order,_d_time in enumerate(_this_truck_departure_time):
                if _relative_node_order == len(_this_truck_departure_time) - 1:
                    # this is the last node
                    break
                if _d_time < base_line_clk + timedelta(minutes=self.future_range) and _d_time >= base_line_clk:
                    # +1 for the corresponding matrix
                    # determine which row it is gonna be
                    # the row time window is (left,right]
                    _gap = _d_time - base_line_clk
                    n_of_row = int(_gap.total_seconds()/60)
                    if _gap.total_seconds() % 60 == 0:
                        n_of_row += -1
                    if n_of_row < 0:
                        n_of_row = 0
                    # we now need to select the edge
                    n_of_col = _truck.edge_list[_relative_node_order]
                    # n_of_col = _truck.node_list[_relative_node_order]
                    _temp[n_of_row,n_of_col] += 1
                else:
                    break
        self.next_period_plan_matrix = _temp
    
    def select_communication_slot(self,max_slot:int):
        self.current_slot_com = random.randint(1,max_slot)

    def random_select_one_neighbor(self,commun_graph:nx.graph) -> int:
        # return the carrier index selected, return -1 if not neighbor
        _neighbors = list(commun_graph.neighbors(self.carrier_index))
        if len(_neighbors) == 0:
            return -1
        return random.choice(_neighbors)
    
    def split_plan_table_into_two_part(self) -> list:
        # self.public_prime = key_prime
        key_prime = self.public_prime
        matrix_shape = self.next_period_plan_matrix.shape
        A = np.random.randint(0, key_prime, size=matrix_shape, dtype=np.int64)
        B = (self.next_period_plan_matrix - A) % key_prime
        return [A,B]

    def row_rolling_plan_table(self,base_line_clk:datetime) -> None:
        self.next_period_plan_matrix[:-1, :] = self.next_period_plan_matrix[1:, :]
        self.next_period_plan_matrix[-1, :] = 0
        concerned_time_slot_left  = base_line_clk + timedelta(self.future_range - self.time_resolution)
        concerned_time_slot_right = concerned_time_slot_left + timedelta(self.time_resolution)
        for _truck in self.truck_list:
            # ask for the latest departure time information again
            _this_list = _truck.generate_depature_time_list()
            # check the if any departure at this row
            for _this_truck_node_index,_d_time in enumerate(_this_list):
                if _d_time >= concerned_time_slot_left and _d_time < concerned_time_slot_right:
                    # there is a departure in this node
                    self.next_period_plan_matrix[_truck.node_list[_this_truck_node_index],-1] += 1
                    break 
                if _d_time >= concerned_time_slot_right:
                    break

    # def update_plan_matrix(self,input1:np.array,input2:np.array) -> None:
    #     self.next_period_plan_matrix = input1 + input2
    
    # def explain_encrypted_matrix(self,input_array:np.array,est_carrier:int) -> np.array:
    #     return round((input_array * est_carrier) % self.public_prime)

    def sync_future_plan(self,requried_hub:list,arrival_time:datetime,current_clk:datetime,truck_index:int,est_carrier:int) -> list:
        # return a list of dictionary of each future hub, the possible depature time for platooning
        # the truck does not care the peers that leave already before

        # But for trucks from other carriers, the information is limited to the consensus period
        # It also requries the carrier to sync the planning of ther trucks in the list

        # FIXME: Arrival time here means the latest arrival time of this truck

        # first floor this clk to a time resolution
        seconds_since_epoch = (current_clk - datetime(1970, 1, 1)).total_seconds()
        rounded_seconds = int(seconds_since_epoch // self.time_resolution) * self.time_resolution
        current_clk = datetime.utcfromtimestamp(rounded_seconds)

        time_gap = arrival_time - current_clk
        In_range_aggreated = {}
        if time_gap <= self.future_range:
            t_a_row = int(time_gap/self.time_resolution) # counting from 0, this row is the start of interested
            for _hub in requried_hub:
                In_range_aggreated_at_hub   = self.next_period_plan_matrix[t_a_row:, _hub]

                In_range_aggreated[_hub]    = self.explain_encrypted_matrix(In_range_aggreated_at_hub,est_carrier)

        # also give the plan in this carrier
        same_carrier_dict = {}
        for _hub in requried_hub:
            same_carrier_list = []
            for _truck in self.truck_list:
                if _truck.truck_index == truck_index:
                # itself does not include
                    continue
                if _hub in _truck.node_list:
                    # this truck has an overlap hub
                    [t_a,t_d] = _truck.answer_my_plan_at_hub(_hub)
                    if t_a >= arrival_time:
                        # potential platooning same-carrier peer
                        same_carrier_list.append(t_a)
            same_carrier_dict[_hub] = same_carrier_list
        
        return [In_range_aggreated,same_carrier_dict]
                
    def answer_known_departure_list_at_this_hub(self,hub_index:int,start_time:datetime,end_time:datetime,table_base_clk:datetime):
        # (my carrier(including yourself), all I know (including yourself))

        # depending on required time window
        agg_depart_time = []
        aggreated_qty   = []
        ego_depart_time = []
        ego_qty         = []

        # start time is the current matrix base
        # so it means everything happens in this timeframe are considered happend together

        if start_time < table_base_clk + timedelta(minutes=self.time_resolution*self.future_range):
            # something to return from the window
            hub_array_raw  = self.next_period_plan_matrix[:,hub_index]
            sum_col        = (hub_array_raw % self.public_prime) * self.carrier_qty_est
            for row_index,row in enumerate(list(sum_col)):
                if row == 0:
                    continue
                else:
                    this_time = start_time + timedelta(minutes=row_index * self.time_resolution)
                    if this_time <= end_time:
                        agg_depart_time.append(this_time)
                        aggreated_qty.append(row)
        
        for _truck in self.truck_list:
            if hub_index in _truck.node_list:
                [t_a,t_d] = _truck.answer_my_plan_at_hub(hub_index)
                if t_d >= start_time and t_d <= end_time:
                    _t_round = t_d.replace(second=0,microsecond=0)
                    # this round time should exist in the list already
                    if _t_round in ego_depart_time:
                        ego_qty[ego_depart_time.index(_t_round)] += 1
                    else:
                        ego_depart_time.append(_t_round)
                        ego_qty.append(1)
        
        if not len(ego_depart_time) == len(agg_depart_time):
            # there is such case that part of the ego plan is not in the agg data, that we align the length of data
            for ego_depart_time_index,ego_depart_time in enumerate(ego_depart_time):
                if not ego_depart_time in agg_depart_time:
                    agg_depart_time.append(ego_depart_time)
                    aggreated_qty.append(ego_qty[ego_depart_time_index]) 
                    # it must be noted that, the ego time may not be properly order

        return aggreated_qty,ego_qty,ego_depart_time,agg_depart_time
    

    def answer_known_departure_list_for_this_edge(self,edge_index:int,start_time:datetime,end_time:datetime,table_base_clk:datetime):
        # the carrier the asking truck, all the carrier knows about depature parteners
        # depending on required time window
        agg_depart_time = [] # all combined
        agg_qty         = []
        ego_depart_time = [] # only this carrier
        ego_qty         = []

        # start time is the current matrix base
        # so it means everything happens in this timeframe are considered happend together
        # (A row in the time plan matrix)
        # self.next_period_agg = self.encrypted_data
        if start_time < table_base_clk + timedelta(minutes=self.time_resolution*self.future_range):
            # something make senses in this window
            edge_array_raw = self.next_period_agg[:,edge_index].copy()
            sum_col        = (edge_array_raw) % self.public_prime

            for row_index,row in enumerate(list(sum_col)):
                if row == 0:
                    continue
                else:
                    this_time = table_base_clk + timedelta(minutes=(row_index + 1) * self.time_resolution)
                    # the depart time is set at the latest of this window
                    if this_time <= end_time:
                        agg_depart_time.append(this_time)
                        agg_qty.append(row)

        for _truck in self.truck_list:
            if edge_index in _truck.edge_list:
                [t_a,t_d] = _truck.answer_my_plan_at_hub(_truck.node_list[_truck.edge_list.index(edge_index)])
                if t_d >= start_time and t_d <= end_time:
                    if t_d.second == 0 and t_d.microsecond == 0:
                        _t_round = t_d
                    else:
                        _t_round = t_d.replace(second=0,microsecond=0) + timedelta(minutes=self.time_resolution)
                    # this round time should exist in the list already
                    if _t_round in ego_depart_time:
                        ego_qty[ego_depart_time.index(_t_round)] += 1
                    else:
                        ego_depart_time.append(_t_round)
                        ego_qty.append(1) 
                     
        if not len(ego_depart_time) == len(agg_depart_time):
            # there is such case that part of the ego plan is not in the agg data, that we align the length of data
            for ego_depart_time_index,ego_depart_time_ele in enumerate(ego_depart_time):
                if not ego_depart_time_ele in agg_depart_time:
                    agg_depart_time.append(ego_depart_time_ele)
                    agg_qty.append(ego_qty[ego_depart_time_index]) 
                    # it must be noted that, the ego time may not be properly order

        return agg_qty,ego_qty,ego_depart_time,agg_depart_time


    def est_current_carrier_number(self) -> None:
        # at some point, this carrier will estimate the current carrier number
        # everytime I perform a new information exchange
        _sum_matrix = self.next_period_plan_matrix % self.public_prime
        non_zero_indices    = np.nonzero(_sum_matrix>0)
        if len(non_zero_indices[0]) == 0:
            # all elements now are zero,
            # the carrier have very bad estimation on only itself is online
            # but this should not happen
            self.carrier_qty_est = 1
        else:
            min_value = np.min(_sum_matrix[non_zero_indices])
            # it is assumed that this value is the average of the sum '1'
            self.carrier_qty_est = math.floor(1/min_value)
        
    def get_current_carrier_number(self,est_qty:int) -> None:
        self.carrier_qty_est = est_qty

    def select_a_random_neighbor(self) -> int:
        return random.choice(self.neighoring_carrier_index)
    
    def decode_agg_truck_table(self,cur_table_base:datetime) -> None:
        # if self.carrier_qty_est > 1:
        #     self.next_period_agg = np.round(self.encrypted_data * self.carrier_qty_est)
        # else:
        #     self.next_period_agg = self.next_period_plan_matrix
        if cur_table_base  - self.enc_data_table_base > timedelta(minutes=self.future_range):
            # there is no information in my enc buffer, it may not even exist
            self.next_period_agg = self.next_period_plan_matrix # use all my information
        else:
            _gap        = (cur_table_base  - self.enc_data_table_base).total_seconds()
            _gap_row    = int(_gap/(self.time_resolution * 60))
            if not _gap_row == 0:
                _temp       = np.round(self.encrypted_data * self.carrier_qty_est)
                _temp_valid = _temp[_gap_row:]
                _ego_comp   = self.next_period_plan_matrix[-_gap_row:]
                self.next_period_agg = np.vstack((_temp_valid,_ego_comp))
            else:
                self.next_period_agg = np.round(self.encrypted_data * self.carrier_qty_est)



    def update_encryption_data(self,base_clk:datetime) -> None:
        new_plan = self.return_current_ego_plan_in_matrix(base_clk)
        diff_mat = new_plan - self.next_period_plan_matrix
        try:
            self.encrypted_data += diff_mat # changes are loaded in
            self.next_period_plan_matrix = new_plan
        except:
            pass

    def return_current_ego_plan_in_matrix(self,base_clk:datetime) -> np.array:
        temp = np.zeros(shape=self.next_period_plan_matrix.shape)
        base_line_clk = base_clk
        for _truck in self.truck_list:
            _this_truck_departure_time = _truck.generate_depature_time_list()
            for _relative_node_order,_d_time in enumerate(_this_truck_departure_time):
                if _relative_node_order == len(_this_truck_departure_time) - 1:
                    # this is the last node
                    break
                if _d_time < base_line_clk + timedelta(minutes=self.future_range) and _d_time >= base_line_clk:
                    # +1 for the corresponding matrix
                    # determine which row it is gonna be
                    _gap = _d_time - base_line_clk
                    n_of_row = int(_gap.total_seconds()/60) - 1
                    if n_of_row < 0:
                        n_of_row = 0
                    # we now need to select the edge
                    n_of_col = _truck.edge_list[_relative_node_order]
                    # n_of_col = _truck.node_list[_relative_node_order]
                    temp[n_of_row,n_of_col] += 1
                else:
                    break
        return temp