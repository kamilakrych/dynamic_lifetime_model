"""
Class DynamicLifetimeModel

Methods for handling dynamic stock models with dynamic lifetime (variable by time and/or by cohort)

Created on 22 Sept 2023

@authors: Kamila Krych, NTNU Trondheim, Norway.
Built on previous work done by Stephan Pauliuk et al. in the dynamic_stock_model and Fernando Aguilar Lopez et al. in the product_component_model. 

standard abbreviation: DLM or dlm 

Repository for this class, documentation, and tutorials: 
https://github.com/kamilakrych/dynamic_lifetime_model

"""

import numpy as np
import scipy.stats
import math

class DynamicLifetimeModel:
    """
    Class containing a dynamic stock model with dynamic lifetime (variable by time and/or by cohort)

    Attributes
    ----------
    t : Series of years or other time intervals
    i : Discrete time series of inflow to stock (c)
    o : Discrete time series of outflow from stock (t)
    o_c :Discrete time series of outflow from stock, by cohort (t,c)
    s : Discrete time series for stock, total (t)
    s_c : Discrete time series for stock, by cohort (t,c)
    ds : Discrete time series for stock change (t)
    lt : lifetime distribution: dictionary with distribution type and parameters, where each parameter is of shape (t,c)
    hz: hazard function for different product cohorts (t,c)
    """

    def __init__(self, t: np.ndarray, i=None, s=None, s_c=None, o=None, o_c=None, ds=None, lt=None, hz=None):
        """
        Basic initialisation
        """
        self.t = t
        self.i = i # optional
        self.o = o # optional
        self.o_c = o_c # optional
        self.s = s # optional
        self.s_c = s_c # optional
        self.ds = ds # optional
        self.lt = lt # optional
        self.hz = hz # optional
        

    def compute_inflow_driven_model(self):
        """ 
        Computes the model given the lifetime distribution and inflows
        """
        if self.i is None:
            raise Exception('No inflows specified')
        elif np.shape(self.i) != np.shape(self.t):
            raise Exception(f'Non-compatible array shapes. Array t has shape {np.shape(self.t)}, but array i has shape {np.shape(self.i)}')
        self.s_c = np.zeros((len(self.t), len(self.t))) # stock composition per year
        self.o_c = np.zeros((len(self.t), len(self.t))) # outflow compositionO
        # construct the hazard function
        self.__compute_hz__()
        for m in range(len(self.t)):
            if m>0: # the initial stock is assumed to be 0
                self.o_c[m,:m] = self.s_c[m-1,:m] * self.hz[m,:m] 
                # subtract outflows of cohorts <m from the previous stock 
                self.s_c[m,:m] = self.s_c[m-1,:m] - self.o_c[m,:m]
            # Add new cohort to stock
            self.s_c[m,m] = self.i[m]
            self.o_c[m,m] = self.s_c[m,m] * self.hz[m,m]
        self.o = self.o_c.sum(axis=1)
        self.s = self.s_c.sum(axis=1)
        return

    def compute_stock_change(self):
        """ Determines stock change from time series for stock. Formula: stock_change(t) = stock(t) - stock(t-1)."""
        if self.s is not None:
            self.ds = np.zeros(len(self.s))
            self.ds[0] = self.s[0]
            self.ds[1::] = np.diff(self.s)
            return self.ds
        else:
            return None

    def compute_stock_driven_model(self): 
        """ 
        Computes the model given the lifetime distribution and the total stock. 
        Inspired by case 1 of the product_component_model by Fernando Aguilar Lopez and colleagues
        """
        if self.s is None:
            raise Exception('No stock specified')
        self.s_c = np.zeros((len(self.t), len(self.t))) # stock composition per year
        self.o_c = np.zeros((len(self.t), len(self.t))) # outflow composition
        self.i = np.zeros(len(self.t)) # product inflows
        self.ds = np.concatenate(([self.s[0]], np.diff(self.s))) # stock change
        # construct the hazard function
        self.__compute_hz__()
        # Initializing values
        self.s_c[0,0] = self.s[0]               
        for m in range(len(self.t)):  # for all years m
            if m>0: # the initial stock is assumed to be 0
                # Probability of any failure is calculated using product hazard function 
                self.o_c[m,:m] = self.s_c[m-1,:m] * self.hz[m,:m] 
                # subtract outflows of cohorts <m from the previous stock 
                self.s_c[m,:m] = self.s_c[m-1,:m] - self.o_c[m,:m]
                # Add new cohort to stock
                self.s_c[m,m] = self.s[m] - self.s_c[m,:m].sum()
           
            # Calculate new inflow, accounting for outflows in the first year
            self.o_c[m,m] = self.s_c[m,m] * self.hz[m,m] 
            self.i[m] = self.ds[m] + self.o_c[m,:].sum()
        self.o = self.o_c.sum(axis=1)
        return


    def __compute_hz__(self):
        """
        Calculates a hazard table self.hz(m,n) which denotes the probability of a product inflow from year n (cohort) 
        failing during year m, still present at the beginning of year m (after m-n years).
        """
        if self.hz is None:
            if self.lt is None:
                raise Exception('No product lifetime specified')
            # find unique sets of lifetime parameters
            unique, inverse, length = self.__find_unique_lt__()
            # calculate sf for each unique parameter set
            hz_unique = np.zeros((len(self.t),length))
            if self.lt['Type'] == 'Fixed':
                for i in range(length): # for each unique parameter set
                    if unique['Mean'][i] != 0:
                        sf = np.multiply(1, (np.arange(len(self.t)) < unique['Mean'][i])) # converts bool to 0/1
                        # calculate hz for each unique parameter set
                        hz_unique[0,i] = 1-sf[0]
                        for m in range(len(self.t)-1): # for each year m
                            if sf[m] != 0:
                                hz_unique[m+1,i] = (sf[m] - sf[m+1]) / sf[m]
                            else: 
                                hz_unique[m+1,i] = 1
            elif self.lt['Type'] == 'Normal':
                for i in range(length): # for each unique parameter set
                    if unique['StdDev'][i] != 0:
                        sf = scipy.stats.norm.sf(np.arange(len(self.t)), loc=unique['Mean'][i], scale=unique['StdDev'][i])
                        # calculate hz for each unique parameter set
                        hz_unique[0,i] = 1-sf[0]
                        for m in range(len(self.t)-1): # for each year m
                            if sf[m] != 0:
                                hz_unique[m+1,i] = (sf[m] - sf[m+1]) / sf[m]
                            else: 
                                hz_unique[m+1,i] = 1
            elif self.lt['Type'] == 'FoldedNormal':
                for i in range(length): # for each unique parameter set
                    if unique['StdDev'][i] != 0:
                        sf = scipy.stats.foldnorm.sf(np.arange(len(self.t)), c=unique['Mean'][i]/unique['StdDev'][i], loc=0, scale=unique['StdDev'][i])
                        # calculate hz for each unique parameter set
                        hz_unique[0,i] = 1-sf[0]
                        for m in range(len(self.t)-1): # for each year m
                            if sf[m] != 0:
                                hz_unique[m+1,i] = (sf[m] - sf[m+1]) / sf[m]
                            else: 
                                hz_unique[m+1,i] = 1
            elif self.lt['Type'] == 'LogNormal': 
                for i in range(length): # for each unique parameter set
                    if unique['StdDev'][i] != 0:
                        # calculate parameter sigma of underlying normal distribution:
                        LT_LN = np.log(unique['Mean'][i] / np.sqrt(1 + unique['Mean'][i] * unique['Mean'][i] / (unique['StdDev'][i] * unique['StdDev'][i]))) 
                        SG_LN = np.sqrt(np.log(1 + unique['Mean'][i] * unique['Mean'][i] / (unique['StdDev'][i] * unique['StdDev'][i])))
                        sf = scipy.stats.lognorm.sf(np.arange(len(self.t)), s=SG_LN, loc = 0, scale=np.exp(LT_LN))
                        # calculate hz for each unique parameter set
                        hz_unique[0,i] = 1-sf[0]
                        for m in range(len(self.t)-1): # for each year m
                            if sf[m] != 0:
                                hz_unique[m+1,i] = (sf[m] - sf[m+1]) / sf[m]
                            else: 
                                hz_unique[m+1,i] = 1
            elif self.lt['Type'] == 'Weibull':
                for i in range(length): # for each unique parameter set
                    if unique['Scale'][i] != 0:
                        sf = scipy.stats.weibull_min.sf(np.arange(len(self.t)), c=unique['Shape'][i], loc = 0, scale=unique['Scale'][i])
                        # calculate hz for each unique parameter set
                        hz_unique[0,i] = 1-sf[0]
                        for m in range(len(self.t)-1): # for each year m
                            if sf[m] != 0:
                                hz_unique[m+1,i] = (sf[m] - sf[m+1]) / sf[m]
                            else: 
                                hz_unique[m+1,i] = 1
            else:
                raise Exception(f"Distribution type {self.lt['Type']} is not implemented")
            # calculate hazard table hz for the entire time-cohort matrix
            self.hz = np.zeros((len(self.t), len(self.t)))
            for n in range(len(self.t)): # for each cohort n
                for m in range(n,len(self.t)): # for each year m
                    self.hz[m,n] = hz_unique[m-n,inverse[m,n]]
            return self.hz
        else:
            # hz already exists
            return self.hz


    def __find_unique_lt__(self):
        """
        Finds unique sets of p lifetime parameters (e.g., for Weibull, the set includes scale and shape), each parameter of shape (t,t).
        :return unique: The dictionary of parameters and their values, such that each set (p1[i], p2[i], ..., pn[i]) is unique. 
        :return inverse: The indices to reconstruct the original lt array from the unique array.
        :return length: Number of unique sets
        """
        params = {k:v for k,v in self.lt.items() if k!= 'Type'}
        sets = np.concatenate([[p] for p in params.values()], axis=0) # stacks all the p parameters
        sets = sets.reshape(len(params),-1) # reshapes from 3D form (p,t,t) into 2D form (p,t*t)
        unique, inverse = np.unique(sets, return_inverse=True, axis=1)
        inverse = inverse.reshape(len(self.t),len(self.t)) # reshapes from 1D form (t*t) into 2D form (t,t)
        length = np.shape(unique)[1]
        unique = {k:unique[p,:] for p,k in enumerate(params.keys())}
        return unique, inverse, length


    def create_lt_from_int(self, value: float or int):
        """
        Creates an array sized (t,t) such that the lower triangle (incl. the diagonal) is filled with the value, 
        and the upper triangle is equal to zero.
        :par value: A value to fill the lower triangle
        :return lt_par: An array of size (t,t)
        """
        lt_par = np.full((len(self.t),len(self.t)), value, dtype=float)
        lt_par = np.tril(lt_par, 0)
        # lt_par[np.triu_indices(lt_par.shape[0], -1)] = np.nan
        return lt_par
    

    def create_lt_from_row(self, array: np.ndarray):
        """
        Creates an array sized (t,t) such that the lower triangle (incl. the diagonal) is filled with the array values (cohort-wise), 
        and the upper triangle is equal to zero.
        :par array: An array of size (t) to fill the lower triangle cohort-wise
        :return lt_par: An array of size (t,t)
        """
        assert (len(array)==len(self.t)), "The array should have the same length as the time vector"
        lt_par = np.repeat(np.reshape(array,(1,len(array))), repeats=len(array), axis=0)
        lt_par = np.tril(lt_par, 0)
        lt_par[lt_par == 0]  = np.nan
        # lt_par[np.triu_indices(lt_par.shape[0], -1)] = np.nan
        return lt_par


    def create_lt_from_column(self, array: np.ndarray):
        """
        Creates an array sized (t,t) such that the lower triangle (incl. the diagonal) is filled with the array values (time-wise), 
        and the upper triangle is equal to zero.
        :par array: An array of size (t) to fill the lower triangle time-wise
        :return lt_par: An array of size (t,t)
        """
        assert (len(array)==len(self.t)), "The array should have the same length as the time vector"
        lt_par = np.repeat(np.reshape(array,(len(array),1)), repeats=len(array), axis=1)
        lt_par = np.tril(lt_par, 0)
        # lt_par[np.triu_indices(lt_par.shape[0], -1)] = np.nan
        return lt_par


    def add_cohort_effect(self, lt_par, value: float or int, start: int, stop: int, ref='absolute'):
        """
        Adds a cohort effect to the given lifetime parameter.
        :par lt_par: An array of size (t,t) with the lifetime parameter
        :par value: Value of the parameter when the effect stops
        :par start: Cohort year when the effect starts
        :par stop: Cohort year when the effect stops
        :par ref: Reference. 'absolute' - the value at stop is equal to 'value', 'relative' - the value at stop is equal to 'value' times the value at start
        :return lt_par: An array of size (t,t) with the modified lifetime parameter
        """
        # TODO: add a flag that will warn if a time effect has been added before this one or if another cohort effect exists that would be wiped out by this one
        # TODO: check if start and stop are within the t array
        start = math.floor(start)
        stop = math.ceil(stop)
        idx = np.where(self.t==start)[0][0]
        value_left = lt_par[idx,idx]
        if ref=='relative':
            value_right=value_left*value
        elif ref=='absolute':
            value_right = value
        else:
            raise Exception("Parameter 'ref' can only take values 'relative' or 'absolute'.")
        for n in range(idx, len(self.t)):
            cohort=self.t[n]
            if cohort < stop:
                lt_par[n:,n] = value_right+(stop-cohort)/(stop-start)*(value_left-value_right)
            else:
                lt_par[n:,n] = value_right
        return lt_par

    
    def add_time_effect(self, lt_par, value: float or int, start: int, stop: int, ref='absolute', trend=None,cohorts=None):
        """
        Adds a time effect to the given lifetime parameter.
        :par lt_par: An array of size (t,t) with the lifetime parameter
        :par value: Value of the parameter when the effect stops
        :par start: Time year when the effect starts
        :par stop: Time year when the effect stops
        :par ref: Reference. 'absolute' - the value at stop is equal to 'value', 'relative' - the value at stop is equal to 'value' times the value at start
        :par trend: default: no trend, all values are changed; 'decreasing' keeps the minimum of the old and the new value, 'increasing' keeps the maximum.
        :par cohorts: A list of cohorts affected by the time effect. Default: all cohorts. 
        :return lt_par: An array of size (t,t) with the modified lifetime parameter
        """
        # TODO: check if start and stop are within the t array
        if cohorts==None:
            cohort_idx = range(len(self.t)) # for each cohort
        else:
            cohort_idx = np.where(np.in1d(self.t,cohorts)==True)[0]
        for n in cohort_idx: # for each cohort
            idx = np.where(self.t==start)[0][0]
            # select the value to start with
            if idx>n:
                value_up = lt_par[idx,n]
            else: # if the time effect starts before the cohort year
                value_up = lt_par[n,n]
            # select the value to end with
            if ref=='relative':
                value_down=value_up*value
            elif ref=='absolute':
                value_down = value
            else:
                raise Exception("Parameter 'how' can only take values 'relative' or 'absolute'.")
            
            for m in range(n,len(self.t)): # for each year
                year = self.t[m]
                v_old = lt_par[m,n]
                # choose the value to assign depending on the year
                if year < start:
                    continue
                elif year < stop:
                    v = value_down+(stop-year)/(stop-start)*(value_up-value_down)
                else:
                    v = value_down
                # keep the trend, e.g., if the values should decrease down to 6, then keep the ones below that unchanged
                if trend=='decreasing':
                    lt_par[m,n] = min(v_old, v)
                elif trend=='increasing':
                    lt_par[m,n] = max(v_old, v)
                else:
                    lt_par[m,n] = v
        return lt_par


    def calculate_age(self, array, isstock: bool, inflows=None):
        """
        Calculates the mean age of a stock or an outflow
        :par array: An array of size (t,c) describing a process stock or outflows by time and cohort
        :par isstock: True if the array describes a stock
        :par inflows: An array of size (t) describing the process inflows. Used to scale the values by inflows in respective years
        :return age: An array of size (t) with the mean age in each year
        """
        try: 
            np.shape(array)[1]
        except:
            raise Exception("Array must have two dimensions")
        if isstock: # stock (measured at the end of each year)
            age_matrix = np.array([self.t]).T - np.array([self.t])+1
            age_matrix[np.triu_indices(age_matrix.shape[0])] = 0
            np.fill_diagonal(age_matrix, 1)
        else: # outflows during the year
            age_matrix = np.array([self.t]).T - np.array([self.t])
            age_matrix[np.triu_indices(age_matrix.shape[0])] = 0
        if inflows is not None:
            array = np.einsum('tc,c->tc', array, self.reciprocal(inflows))
        
        shares = np.einsum('tc,t->tc',array, self.reciprocal(array.sum(axis=1))) # calculate the distribution of cohorts in each year (shares of the total)
        age = np.einsum('tc,tc->t',shares,age_matrix)
        return age


    def reciprocal(self, array):
        """
        Calculates the element-wise reciprocal of an array while ignoring zero values (to avoid Nan values)
        :par array: A numpy array
        :return new_array: A reciprocal array with zero values left unchanged
        """
        mask = array != 0
        with np.errstate(divide='ignore'):
            new_array = 1 / array
        new_array[mask == 0] = 0
        return new_array