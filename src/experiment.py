import numpy as np
import time
import os
import json

from src.network import Layer
from uuid import uuid4


class Experiment:

    __DESCR_FILE = 'experiment_descr.json'
    __LAYER_FILE = 'experiment_layer'
    __NPZ = 'experiment_results.npz'
    __ANNOTATIONS = 'experment_annotations.json'

    def __init__(self, inputs, layer, num_trials, dt, t_stop, num_neurons=None, annotations=None):
        self.layer = layer

        self.num_trials = num_trials
        self.dt = dt
        self.t_stop = t_stop
        self.num_t = np.arange(0.0, t_stop, dt).shape[0]

        self.inputs = inputs
        self.num_neurons = num_neurons
        self.outputs = np.empty(inputs.shape) if num_neurons is None else np.empty(inputs.shape + (num_neurons,))
        self.spike_times = []
        self.spike_neurons = []

        self.annotations = annotations

        self.runtime = None

    def one_trial(self, i, int_noise_regen=True):
        out, _, f_binary, _ = self.layer.output(self.inputs[:, i, None],
                                                self.dt,
                                                self.t_stop,
                                                int_noise_regen)
        times, neurons = np.where(f_binary != 0)
        self.spike_times.append([times])
        self.spike_neurons.append([neurons])
        self.outputs[:, i] = out.flatten() if self.num_neurons is None else out

    def add_trials(self, i, out, f_binary):
        times, neurons = np.where(f_binary != 0)
        self.spike_times.append([times])
        self.spike_neurons.append([neurons])
        self.outputs[:, i] = out.flatten() if self.num_neurons is None else out

    def run(self, status_freq=10):
        start_time = time.time()
        loop_time = start_time

        for i in range(self.num_trials):
            self.one_trial(i)

            if i % status_freq == 0:
                print("Trial ", i)
                print(status_freq, " Iter time: ", time.time() - loop_time)
                print("Total time: ", time.time() - start_time)
                print("\n")
                loop_time = time.time()

        self.runtime = time.time() - start_time
        print("EXPERIMENT FINISHED: ", self.runtime)

    def save(self, path, experiment_name):
        folder_name = experiment_name
        folder_path = os.path.join(path, folder_name)

        while os.path.exists(folder_path):
            folder_name += "_c"
            folder_path = os.path.join(path, folder_name)
        os.makedirs(folder_path)

        with open(os.path.join(folder_path, Experiment.__DESCR_FILE), 'w')\
                as outfile:
            json.dump(self._as_dict(), outfile)
        
        if self.annotations:
            with open(os.path.join(folder_path, Experiment.__ANNOTATIONS), 'w')\
                    as outfile:
                json.dump(self.annotations, outfile)

        self.layer.save(folder_path, Experiment.__LAYER_FILE)

        np.savez(open(os.path.join(folder_path, Experiment.__NPZ), 'wb'),
            inputs=self.inputs,
            outputs=self.outputs,
            spike_times=self.spike_times,
            spike_neurons=self.spike_neurons)

    @classmethod
    def load(cls, path: str, experiment_name: str) -> 'Experiment':
        folder_path = os.path.join(path, experiment_name)

        if not os.path.exists(folder_path):
            raise FileNotFoundError()
        
        in_dict = {}
        infile = open(os.path.join(folder_path, Experiment.__DESCR_FILE), 'r')
        in_dict = json.load(infile)
        num_trials = in_dict['num_trials']
        dt = in_dict['dt']
        t_stop = in_dict['t_stop']
        num_t = in_dict['num_t']
        infile.close()

        annotations = None
        if os.path.exists(os.path.join(folder_path, Experiment.__ANNOTATIONS)):
            infile = open(os.path.join(folder_path, Experiment.__ANNOTATIONS), 'r')
            annotations = json.load(infile)
            infile.close()

        layer = Layer.load(folder_path, Experiment.__LAYER_FILE)

        in_npys = np.load(open(os.path.join(folder_path, Experiment.__NPZ),
                               'rb'), allow_pickle=True)
        inputs = in_npys['inputs']
        outputs = in_npys['outputs']
        spike_times = in_npys['spike_times']
        spike_neurons = in_npys['spike_neurons']

        experiment = cls(inputs, layer, num_trials, dt, t_stop)
        experiment.num_t = num_t
        experiment.outputs = outputs
        experiment.spike_times = spike_times
        experiment.spike_neurons = spike_neurons
        experiment.annotations = annotations

        return experiment

    def _as_dict(self):
        return {
            'num_trials': self.num_trials,
            'dt': self.dt,
            't_stop': self.t_stop,
            'num_t': self.num_t
        }

    def spike_graph(self):
        spikes = np.zeros((self.num_t, self.layer.NUM_NEURONS, self.num_trials))

        for i in range(self.num_trials):
            spikes[self.spike_times[i], self.spike_neurons[i], i] = 1.0

        return spikes


class MultiVariableExperiment:

    __DESCR_FILE = 'mve_descr.json'
    __ANNOTATIONS = 'mve_annotations.json'
    __VAR_VALUES_UUID = 'mve_var_values_uuid.json'

    def __init__(self, variables: dict, num_trials, dt, t_stop, annotations=None):
        """

        Args:
            variables (dict): Dictionary of form
                {'var1': {'start': , 'stop': , 'step': }, ...}
            inputs:
            layers:
            num_trials:
            dt:
            t_stop:
        """
        self.vars = variables

        self.experiments = {}
        self.var_values_dict = {}

        self.dt = dt
        self.t_stop = t_stop
        self.num_t = np.arange(0.0, t_stop, dt).shape[0]

        self.num_trials = num_trials

        self.annotations=annotations

    def one_experiment(self, var_values: dict, inputs: np.ndarray, layer: Layer, path: str, experiment_name: str) -> Experiment:
        var_values_uuid = str(uuid4())

        experiment = Experiment(inputs, layer, self.num_trials, self.dt, self.t_stop, annotations=var_values_uuid)
        experiment.run(status_freq=self.num_trials)

        self.var_values_dict[var_values_uuid] = var_values
        self._save_one_experiment(path, experiment_name, experiment, var_values_uuid)

        return experiment

    def add_one_experiment(self, var_values: dict, experiment: Experiment, var_values_uuid) -> Experiment:
        self.var_values_dict[var_values_uuid] = var_values
        self.experiments[var_values_uuid] = experiment

    def _as_dict(self):
        return {
            'vars': self.vars,
            'num_trials': self.num_trials,
            'dt': self.dt,
            't_stop': self.t_stop,
            'num_t': self.num_t
        }

    def _save_one_experiment(self, path: str, experiment_name: str, experiment: Experiment, experiment_uuid):
        folder_path = os.path.join(path, experiment_name)

        self.save(path, experiment_name)

        self._save_mve_descr_file(folder_path)

        var_values = self.var_values_dict[experiment_uuid]
        print(experiment_uuid)
        print(var_values)
        print(MultiVariableExperiment.var_values_to_str(experiment_uuid, var_values))
        experiment.save(path=folder_path, experiment_name=MultiVariableExperiment.var_values_to_str(experiment_uuid, var_values))

    def save(self, path: str, experiment_name: str) -> Experiment:
        folder_path = os.path.join(path, experiment_name)

        if not os.path.exists(folder_path):
            os.makedirs(folder_path)

        # for var_values_uuid, experiment in self.experiments.items():
        #     var_values = self.var_values_dict[var_values_uuid]
        #     experiment.save(path=folder_path, experiment_name=MultiVariableExperiment.var_values_to_str(var_values_uuid, var_values))

        self._save_mve_descr_file(folder_path)
        self._save_var_values_uuid(folder_path)
        self._save_mve_annotations(folder_path)

    def _save_mve_annotations(self, folder_path):
        if self.annotations:
            with open(os.path.join(folder_path, MultiVariableExperiment.__ANNOTATIONS), 'w')\
                    as outfile:
                json.dump(self.annotations, outfile)

    def _save_mve_descr_file(self, folder_path):
        with open(os.path.join(folder_path, MultiVariableExperiment.__DESCR_FILE), 'w')\
            as outfile:
            json.dump(self._as_dict(), outfile)

    def _save_var_values_uuid(self, folder_path):
        with open(os.path.join(folder_path, MultiVariableExperiment.__VAR_VALUES_UUID), 'w') as outfile:
            json.dump(self.var_values_dict, outfile)

    def load_one_experiment(self, path: str, experiment_name: str, var_values_uuid) -> Experiment:
        folder_path = check_folder_path(path, experiment_name)
        for exp_name in os.listdir(folder_path):
            if os.path.isdir(os.path.join(folder_path, exp_name)):
                experiment = Experiment.load(folder_path, exp_name)
                if experiment.annotations == var_values_uuid:
                    return experiment
        return None

    @classmethod
    def load(cls, path: str, experiment_name: str) -> 'MultiVariableExperiment':
        experiments = {}
        folder_path = check_folder_path(path, experiment_name)

        var_values_dict = None
        with open(os.path.join(folder_path, MultiVariableExperiment.__VAR_VALUES_UUID), 'r') as infile:
            var_values_dict = json.load(infile)

        # for exp_name in os.listdir(folder_path):
        #     if os.path.isdir(exp_name):
        #         experiment = Experiment.load(folder_path, exp_name) 
        #         experiments[experiment.annotations] = experiment

        in_dict = {}
        infile = open(os.path.join(folder_path, MultiVariableExperiment.__DESCR_FILE), 'r')
        in_dict = json.load(infile)
        num_trials = in_dict['num_trials']
        dt = in_dict['dt']
        t_stop = in_dict['t_stop']
        variables = in_dict['vars']
        infile.close()

        annotations = None
        if os.path.exists(os.path.join(folder_path, MultiVariableExperiment.__ANNOTATIONS)):
            infile = open(os.path.join(folder_path, MultiVariableExperiment.__ANNOTATIONS), 'r')
            annotations = json.load(infile)
            infile.close()

        mve = cls(variables, num_trials, dt, t_stop, annotations)
        mve.experiments = experiments
        mve.var_values_dict = var_values_dict

        return mve

    @staticmethod
    def var_values_to_str(var_values_uuid, var_values):
        ret_s = str(var_values_uuid)
        for val_name, val in var_values.items():
            ret_s += val_name
            ret_s += "="
            ret_s += str(val)
            ret_s += "__"
        return ret_s

def check_folder_path(path: str, experiment_name: str):
    folder_path = os.path.join(path, experiment_name)

    if not os.path.exists(folder_path):
        raise FileNotFoundError()
    
    return folder_path
# int_noises = range(5, 50, 5)
# network_sizes = range(10, 1110, 100)
# variables = {
#     'int_noise': int_noises,
#     'network_size': network_sizes
# }
# mve = MultiVariableExperiment(variables, num_trials=10, dt, t_stop)

# for int_noise in int_noises:
#     for network_size in network_sizes:
#         var_values = {'int_noise': int_noise, 'network_size': network_size}
#         mve.one_experiment(var_values, inputs, layer)

