#!/usr/bin/env python
# -*- coding: utf-8 -*-
# DCASE 2022
# Task 1: low-complexity ASC with Multiple Devices
# Baseline system
# ---------------------------------------------
# Author: Irene Martin Morato
# Based on the code dcase 2020 task A baseline from Toni Heittola
# Tampere University / Audio Research Group
# License: MIT

import dcase_util
import numpy
import sed_eval
from utils import *
import tensorflow as tf
from TAUUrbanAcousticScenes_2022_Mobile_DevelopmentSet import TAUUrbanAcousticScenes_2022_Mobile_DevelopmentSet
from IPython import embed

__version_info__ = ('1', '0', '0')
__version__ = '.'.join(__version_info__)


def main():
    # Read application default parameter file
    parameters = dcase_util.containers.DictContainer().load(
        filename='task1.yaml'
    )

    # Initialize application parameters
    param = dcase_util.containers.DCASEAppParameterContainer(
        parameters,
        path_structure={
            'LEARNER': ['DATA_PROCESSING_CHAIN', 'LEARNER'],
            'RECOGNIZER': ['DATA_PROCESSING_CHAIN', 'LEARNER', 'RECOGNIZER'],
        }
    )

    # Handle application arguments
    args, overwrite = handle_application_arguments(
        app_parameters=param,
        raw_parameters=parameters,
        application_title='Task 1A: low-complexity Acoustic Scene Classification',
        version=__version__
    )

    # Process parameters, this is done only after application argument handling in case
    # parameters where injected from command line.
    param.process()

    if args.parameter_set:
        # Check parameter set ids given as program arguments
        parameters_sets = args.parameter_set.split(',')

        # Check parameter_sets
        for set_id in parameters_sets:
            if not param.set_id_exists(set_id=set_id):
                raise ValueError('Parameter set id [{set_id}] not found.'.format(set_id=set_id))

    else:
        parameters_sets = [param.active_set()]

    # Set application mode
    application_mode = 'eval'

    # Get overwrite flag
    if overwrite is None:
        overwrite = param.get_path('general.overwrite')

    # Make sure all system paths exists
    dcase_util.utils.Path().create(
        paths=list(param['path'].values())
    )

    # Setup logging
    dcase_util.utils.setup_logging(
        logging_file=os.path.join(param.get_path('path.log'), 'task1.log')
    )

    # Get logging interface
    log = dcase_util.ui.ui.FancyLogger()

    # Log title
    log.title('DCASE2022 / Task1A -- low-complexity Acoustic Scene Classification')
    log.line()

    if args.show_results:
        # Show evaluated systems
        show_results(param=param, log=log)
        sys.exit(0)

    if args.show_set_list:
        show_parameter_sets(param=param, log=log)
        sys.exit(0)

    # Create timer instance
    timer = dcase_util.utils.Timer()

    for parameter_set in parameters_sets:

        # Set parameter set
        param['active_set'] = parameter_set
        param.update_parameter_set(parameter_set)

        # Get dataset and initialize
        db = TAUUrbanAcousticScenes_2022_Mobile_DevelopmentSet(
            storage_name=param.get_path('dataset.parameters.dataset'),
            data_path=param.get_path('path.dataset'),
        )
        # Part of the initialize data, not everything bc the dataset has been extracted separately
        # Prepare meta data for the dataset class.
        db.prepare()
        # Check meta data and cross validation setup

        # Application working in normal mode aka 'dev' mode
        active_folds = db.folds(
            mode=param.get_path('dataset.parameters.evaluation_mode')
        )

        # Get active fold list from parameters
        active_fold_list = param.get_path('general.active_fold_list')

        if active_fold_list and len(set(active_folds).intersection(active_fold_list)) > 0:
            # Active fold list is set and it intersects with active_folds given by dataset class
            active_folds = list(set(active_folds).intersection(active_fold_list))

        # Print some general information
        show_general_information(
            parameter_set=parameter_set,
            active_folds=active_folds,
            param=param,
            db=db,
            log=log
        )

        if param.get_path('flow.learning'):
            # Learning stage
            log.section_header('Learning')

            timer.start()

            processed_items = do_learning(
                db=db,
                folds=active_folds,
                param=param,
                log=log,
                overwrite=overwrite

            )

            timer.stop()

            log.foot(
                time=timer.elapsed(),
                item_count=len(processed_items)
            )

        # System evaluation in 'dev' mode
        if param.get_path('flow.testing'):
            # Testing stage
            log.section_header('Testing')

            timer.start()

            # temp_scene_labels = ['airport','bus', 'metro','metro_station','park','public_square','shopping_mall','street_pedestrian','street_traffic', 'tram']
            processed_items = do_testing(
                db=db,
                scene_labels=db.scene_labels(),
                folds=active_folds,
                param=param,
                log=log,
                overwrite=overwrite

            )

            timer.stop()

            log.foot(
                time=timer.elapsed(),
                item_count=len(processed_items)
            )

            if args.output_file:
                save_system_output(
                    db=db,
                    folds=active_folds,
                    param=param,
                    log=log,
                    output_file=args.output_file
                )

        if param.get_path('flow.evaluation'):
            # Evaluation stage
            log.section_header('Evaluation')

            timer.start()

            do_evaluation(
                db=db,
                param=param,
                log=log,
                application_mode=application_mode
            )
            timer.stop()

            log.foot(
                time=timer.elapsed(),
            )

        if param.get_path('flow.calculate_model_size'):
            log.section_header('Model size calculation')

            timer.start()

            do_model_size_calculation(
                folds=active_folds,
                param=param,
                log=log,
            )
            log.foot(
                time=timer.elapsed(),
            )

    return 0


def do_learning(db, folds, param, log, overwrite=False):
    """Learning stage

    Parameters
    ----------
    db : dcase_util.dataset.Dataset
        Dataset

    db_h5 : h5 features

    folds : list
        List of active folds

    param : dcase_util.containers.DCASEAppParameterContainer
        Application parameters

    log : dcase_util.ui.FancyLogger
        Logging interface

    overwrite : bool
        Overwrite data always
        Default value False

    Returns
    -------
    nothing

    """

    # Loop over all cross-validation folds and learn acoustic models

    processed_files = []

    for fold in folds:
        log.line(
            data='Fold [{fold}]'.format(fold=fold),
            indent=2
        )

        fold_model_filename = os.path.join(
            param.get_path('path.application.learner'),
            'model.tflite'
        )
        if not os.path.isfile(fold_model_filename) or overwrite:
            log.line()

            if param.get_path('learner.parameters.validation_set') and param.get_path(
                    'learner.parameters.validation_set.enable', True):
                # Get validation files
                training_files, validation_files = db.validation_split(
                    fold=fold,
                    split_type='balanced',
                    validation_amount=param.get_path('learner.parameters.validation_set.validation_amount'),
                    balancing_mode=param.get_path('learner.parameters.validation_set.balancing_mode'),
                    seed=param.get_path('learner.parameters.validation_set.seed', 0),
                    verbose=True
                )

            else:
                # No validation set used
                training_files = db.train(fold=fold).unique_files
                validation_files = dcase_util.containers.MetaDataContainer()

            # Create item_list_train and item_list_validation
            item_list_train = []
            item_list_validation = []
            for item in db.train(fold=fold):
                # Get feature filename
                feature_filename = os.path.basename(item.filename)
                if item.filename in validation_files:
                    item_list_validation.append(feature_filename)

                elif item.filename in training_files:
                    item_list_train.append(feature_filename)

            # Setup keras, run only once
            dcase_util.tfkeras.setup_keras(
                seed=param.get_path('learner.parameters.random_seed'),
                profile=param.get_path('learner.parameters.keras_profile'),
                backend=param.get_path('learner.parameters.backend', 'tensorflow'),
                print_indent=2
            )

            # Collect training data and corresponding targets to matrices
            # FROM THE H5 files
            log.line('Collecting training data', indent=2)
            X_train, Y_train, data_size = load_data(db.scene_labels(), item_list_train, param, split='Train')
            X_train = tf.expand_dims(X_train, -1)
            Y_train = tf.expand_dims(Y_train, -1)

            log.foot(indent=2)

            if item_list_validation:
                log.line('Collecting validation data', indent=2)
                X_validation, Y_validation, data_size = load_data(db.scene_labels(), item_list_validation, param, split='Val')
                X_validation = tf.expand_dims(X_validation, -1)
                Y_validation = tf.expand_dims(Y_validation, -1)

                log.foot(indent=2)

                validation_data = (X_validation, Y_validation)

            else:
                validation_data = None

            # Collect constants for the model generation, add class count and feature matrix size
            model_parameter_constants = {
                'CLASS_COUNT': int(db.scene_label_count()),
                'FEATURE_VECTOR_LENGTH': int(data_size['data']), # 40
                'INPUT_SEQUENCE_LENGTH': int(data_size['time']), # 51
            }

            # Read constants from parameters
            model_parameter_constants.update(
                param.get_path('learner.parameters.model.constants', {})
            )

            # Create sequential model
            keras_model = create_sequential_model( #dcase_util.tfkeras.create_sequential_model(
                model_parameter_list=param.get_path('learner.parameters.model.config'),
                constants=model_parameter_constants
            )

            # Create optimizer object
            param.set_path(
                path='learner.parameters.compile.optimizer',
                new_value=dcase_util.tfkeras.create_optimizer(
                    class_name=param.get_path('learner.parameters.optimizer.class_name'),
                    config=param.get_path('learner.parameters.optimizer.config')
                )
            )

            # Compile model
            keras_model.compile(
                **param.get_path('learner.parameters.compile', {})
            )

            # Show model topology
            log.line(
                dcase_util.tfkeras.model_summary_string(keras_model)
            )
            return

            # Create callback list
            callback_list = [
                dcase_util.tfkeras.ProgressLoggerCallback(
                    epochs=param.get_path('learner.parameters.fit.epochs'),
                    metric=param.get_path('learner.parameters.compile.metrics')[0],
                    loss=param.get_path('learner.parameters.compile.loss'),
                    output_type='logging'
                )
            ]

            if param.get_path('learner.parameters.callbacks.StopperCallback'):
                # StopperCallback
                callback_list.append(
                    dcase_util.tfkeras.StopperCallback(
                        epochs=param.get_path('learner.parameters.fit.epochs'),
                        **param.get_path('learner.parameters.callbacks.StopperCallback', {})
                    )
                )

            if param.get_path('learner.parameters.callbacks.ProgressPlotterCallback'):
                # ProgressPlotterCallback
                callback_list.append(
                    dcase_util.tfkeras.ProgressPlotterCallback(
                        epochs=param.get_path('learner.parameters.fit.epochs'),
                        **param.get_path('learner.parameters.callbacks.ProgressPlotterCallback', {})
                    )
                )

            if param.get_path('learner.parameters.callbacks.StasherCallback'):
                # StasherCallback
                callback_list.append(
                    dcase_util.tfkeras.StasherCallback(
                        epochs=param.get_path('learner.parameters.fit.epochs'),
                        **param.get_path('learner.parameters.callbacks.StasherCallback', {})
                    )
                )

            if param.get_path('learner.parameters.callbacks.LearningRateWarmRestart'):
                # LearningRateWarmRestart
                callback_list.append(
                    dcase_util.tfkeras.LearningRateWarmRestart(
                        nbatch=numpy.ceil(X_train.shape[0] / param.get_path('learner.parameters.fit.batch_size')),
                        **param.get_path('learner.parameters.callbacks.LearningRateWarmRestart', {})
                    )
                )

            # Train model
            keras_model.fit(
                x=X_train,
                y=Y_train,
                validation_data=validation_data,
                callbacks=callback_list,
                verbose=0,
                epochs=param.get_path('learner.parameters.fit.epochs'),
                batch_size=param.get_path('learner.parameters.fit.batch_size'),
                shuffle=param.get_path('learner.parameters.fit.shuffle')
            )

            for callback in callback_list:
                if isinstance(callback, dcase_util.tfkeras.StasherCallback):
                    # Fetch the best performing model
                    callback.log()
                    best_weights = callback.get_best()['weights']

                    if best_weights:
                        keras_model.set_weights(best_weights)

                    break


            # Quantization to int8
            # A generator that provides a representative dataset
            # batch_generator = BatchGenerator(param.get_path('features.path'), batch_size=100)
            # Quantization to int8
            # converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
            # converter.optimizations = [tf.lite.Optimize.DEFAULT] # converts to int32
            # converter.representative_dataset = batch_generator
            # converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
            # converter.inference_input_type = tf.int8  # or tf.uint8   # Initial value was [tf.int8]
            # converter.inference_output_type = tf.int8  # or tf.uint8   # Initial value was [tf.int8]
            # tflite_model = converter.convert()

            # save uncompressed model as h5
            fold_model_filename_h5 = os.path.join(
                param.get_path('path.application.learner'),
                'model.h5'
            )
            keras_model.save(fold_model_filename_h5)

            # Save the quantized model
            save_model_as_tflite(keras_model, param, fold_model_filename)

            # Save the quantized model
            # with open(fold_model_filename, "wb") as output_file:
                # output_file.write(tflite_model)

            processed_files.append(fold_model_filename)

    return processed_files

def create_sequential_model(model_parameter_list, input_shape=None, output_shape=None, constants=None, return_functional=False):
    """Create sequential Keras model

    Example parameters::

        model_parameter_list = [
            {
                'class_name': 'Dense',
                'config': {
                    'units': 'CONSTANT_B',
                    'kernel_initializer': 'uniform',
                    'activation': 'relu'
                }
            },
            {
                'class_name': 'Dropout',
                'config': {
                    'rate': 0.2
                }
            },
            {
                'class_name': 'Dense',
                'config': {
                    'units': 'CONSTANT_A' * 2,
                    'kernel_initializer': 'uniform',
                    'activation': 'relu'
                }
            },
            {
                'class_name': 'Dropout',
                'config': {
                    'rate': 0.2
                }
            },
            {
                'class_name': 'Dense',
                'config': {
                    'units': 'CLASS_COUNT',
                    'kernel_initializer': 'uniform',
                    'activation': 'softmax'
                }
            }
        ]
        constants = {
            'CONSTANT_A': 50,
            'CONSTANT_B': 100
        }

    Parameters
    ----------
    model_parameter_list : dict or DictContainer
        Model parameters

    input_shape : int
        Size of the input layer
        Default value None

    output_shape : int
        Size of the output layer
        Default value None

    constants : dict or DictContainer
        Constants used in the model_parameter definitions.
        Default value None

    return_functional : bool
        Convert sequential model into function model.
        Default value False

    Returns
    -------
    Keras model

    """

    from tensorflow.keras.models import Sequential
    from dcase_util.containers import DictContainer
    import logging
    from dcase_util.utils import SimpleMathStringEvaluator, setup_logging, is_jupyter
    import importlib

    keras_model = Sequential()

    tuple_fields = [
        'input_shape',
        'kernel_size',
        'pool_size',
        'dims',
        'target_shape',
        'strides'
    ]

    # Get constants for model
    if constants is None:
        constants = {}

    if 'INPUT_SHAPE' not in constants and input_shape is not None:
        constants['INPUT_SHAPE'] = input_shape

    if 'OUTPUT_SHAPE' not in constants and output_shape is not None:
        constants['OUTPUT_SHAPE'] = output_shape

    if 'CLASS_COUNT' not in constants:
        constants['CLASS_COUNT'] = output_shape

    if 'FEATURE_VECTOR_LENGTH' not in constants:
        constants['FEATURE_VECTOR_LENGTH'] = input_shape

    def logger():
        logger_instance = logging.getLogger(__name__)
        if not logger_instance.handlers:
            setup_logging()
        return logger_instance

    def process_field(value, constants_dict):
        math_eval = SimpleMathStringEvaluator()

        if isinstance(value, str):
            sub_fields = value.split()
            if len(sub_fields) > 1:
                # Inject constants to math formula
                for subfield_id, subfield in enumerate(sub_fields):
                    if subfield in constants_dict:
                        sub_fields[subfield_id] = str(constants_dict[subfield])
                value = ''.join(sub_fields)

            else:
                # Inject constants
                if value in constants_dict:
                    value = str(constants_dict[value])

            return math_eval.eval(value)

        elif isinstance(value, list):
            processed_value_list = []
            for item_id, item in enumerate(value):
                processed_value_list.append(
                    process_field(
                        value=item,
                        constants_dict=constants_dict
                    )
                )

            return processed_value_list

        else:
            return value

    # Inject constant into constants with equations
    for field in list(constants.keys()):
        constants[field] = process_field(
            value=constants[field],
            constants_dict=constants
        )

    # Setup layers
    for layer_id, layer_setup in enumerate(model_parameter_list):
        # Get layer parameters
        layer_setup = DictContainer(layer_setup)

        if 'config' not in layer_setup:
            layer_setup['config'] = {}

        # Get layer class
        try:
            #print("Layer value is {}".format(layer_setup['class_name']))
            if layer_setup['class_name'] == 'CausalConv1D':
                #print("\tTrying for Casual")
                layer_class = getattr(
                    importlib.import_module('causal_conv1d'),
                    layer_setup['class_name']
                )
            elif layer_setup['class_name'] == 'TCN':
                layer_class = getattr(
                    importlib.import_module('tcn'),
                    'TCN'
                )
            else :
                #print("\tTrying keras")
                layer_class = getattr(
                    importlib.import_module('tensorflow.keras.layers'),
                    layer_setup['class_name']
                )

        except AttributeError:
            message = 'Invalid Keras layer type [{type}].'.format(
                type=layer_setup['class_name']
            )
            logger().exception(message)
            raise AttributeError(message)

        # Inject constants
        for config_field in list(layer_setup['config'].keys()):
            layer_setup['config'][config_field] = process_field(
                value=layer_setup['config'][config_field],
                constants_dict=constants
            )

        # Convert lists into tuples
        for field in tuple_fields:
            if field in layer_setup['config'] and isinstance(layer_setup['config'][field], list):
                layer_setup['config'][field] = tuple(layer_setup['config'][field])

        # Inject input shape for Input layer if not given
        if layer_id == 0 and layer_setup.get_path('config.input_shape') is None and input_shape is not None:
            # Set input layer dimension for the first layer if not set
            layer_setup['config']['input_shape'] = (input_shape,)

        if 'wrapper' in layer_setup:
            # Get layer wrapper class
            try:
                wrapper_class = getattr(
                    importlib.import_module("tensorflow.keras.layers"),
                    layer_setup['wrapper']
                )

            except AttributeError:
                message = 'Invalid Keras layer wrapper type [{type}].'.format(
                    type=layer_setup['wrapper']
                )
                logger().exception(message)
                raise AttributeError(message)
            wrapper_parameters = layer_setup.get('config_wrapper', {})

            if layer_setup.get('config'):
                keras_model.add(
                    wrapper_class(layer_class(**dict(layer_setup.get('config'))), **dict(wrapper_parameters)))
            else:
                keras_model.add(wrapper_class(layer_class(), **dict(wrapper_parameters)))
        else:
            if layer_setup.get('config'):
                keras_model.add(layer_class(**dict(layer_setup.get('config'))))
            else:
                keras_model.add(layer_class())


    if return_functional:
        from tensorflow.keras.layers import Input
        from tensorflow.keras.models import Model
        input_layer = Input(batch_shape=keras_model.layers[0].input_shape)
        prev_layer = input_layer
        for layer in keras_model.layers:
            prev_layer = layer(prev_layer)

        keras_model = Model(
            inputs=[input_layer],
            outputs=[prev_layer]
        )

    return keras_model

def save_model_as_tflite(keras_model, param, fold_model_filename):
    # Quantization to int8
    converter = tf.lite.TFLiteConverter.from_keras_model(keras_model)
    converter.optimizations = [tf.lite.Optimize.DEFAULT] # converts to int32

    # A generator that provides a representative dataset
    batch_generator = BatchGenerator(param.get_path('features.path'), batch_size=100)
    converter.representative_dataset = batch_generator
    converter.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]

    # converter.inference_input_type = tf.int8  # or tf.uint8   # Initial value was [tf.int8]
    # converter.inference_output_type = tf.int8  # or tf.uint8   # Initial value was [tf.int8]
    tflite_model = converter.convert()

    # Save the quantized model
    with open(fold_model_filename, "wb") as output_file:
        output_file.write(tflite_model)


def do_testing(db, scene_labels, folds, param, log, overwrite=False):
    """Testing stage

    Parameters
    ----------
    db : dcase_util.dataset.Dataset
        Dataset

    scene_labels : list of str
        List of scene labels

    folds : list
        List of active folds

    param : dcase_util.containers.DCASEAppParameterContainer
        Application parameters

    log : dcase_util.ui.FancyLogger
        Logging interface

    overwrite : bool
        Overwrite data always
        Default value False

    Returns
    -------
    list

    """

    processed_files = []

    # Get model filename
    fold_model_filename = os.path.join(
        param.get_path('path.application.learner'),
        'model.tflite'
    )

    # --- START COMMENT ---
    # Load h5 model
    '''fold_model_filename_h5 = os.path.join(
        param.get_path('path.application.learner'),
        'model.h5'
    )
    import tcn
    keras_model = tf.keras.models.load_model(fold_model_filename_h5, custom_objects={'TCN':tcn.TCN})

    # save as tflite
    save_model_as_tflite(keras_model, param, fold_model_filename)'''
    # --- END COMMENT ---

    #keras_model = tf.saved_model.load(os.path.join(param.get_path('path.application.learner') ))

    # Loop over all cross-validation folds and test
    for fold in folds:
        log.line(
            data='Fold [{fold}]'.format(fold=fold),
            indent=2
        )


        # Load the model into an interpreter
        interpreter = tf.lite.Interpreter(model_path=fold_model_filename)
        interpreter.allocate_tensors()

        # Get results filename
        fold_results_filename = os.path.join(
            param.get_path('path.application.recognizer'),
            'res_fold_{fold}.csv'.format(fold=fold)
        )

        if not os.path.isfile(fold_results_filename) or overwrite:

            # Initialize results container
            res = dcase_util.containers.MetaDataContainer(
                filename=fold_results_filename
            )

            if not len(db.test(fold=fold)):
                raise ValueError('Dataset did not return any test files. Check dataset setup.')


            # Get input and output indexes for the interpreter
            input_details = interpreter.get_input_details()[0]
            output_details = interpreter.get_output_details()[0]

            # Loop through all test files from the current cross-validation fold
            test_files = db.test(fold=fold)
            index_files = get_index(param, test_files)
            features, _, filenames = get_data(param.get_path('features.path'), index_files)
            for i, feat in enumerate(features):
                # Get feature filename
                filename = filenames[i]
                feat = np.expand_dims(feat, 0).astype(input_details["dtype"])
                input_data = tf.expand_dims(feat, -1)

                # Get network output
                interpreter.set_tensor(input_details['index'], input_data)
                interpreter.invoke()
                output = interpreter.get_tensor(output_details['index'])
                probabilities = output.T
                # Clean up internal states.
                interpreter.reset_all_variables()

                if param.get_path('recognizer.collapse_probabilities.enable', True):
                    probabilities = dcase_util.data.ProbabilityEncoder().collapse_probabilities(
                        probabilities=probabilities,
                        operator=param.get_path('recognizer.collapse_probabilities.operator', 'sum'),
                        time_axis=1
                    )

                # Binarization of the network output
                frame_decisions = dcase_util.data.ProbabilityEncoder().binarization(
                    probabilities=probabilities,
                    binarization_type=param.get_path('recognizer.frame_binarization.type', 'global_threshold'),
                    threshold=param.get_path('recognizer.frame_binarization.threshold', 0.5)
                )

                estimated_scene_label = dcase_util.data.DecisionEncoder(
                    label_list=scene_labels
                ).majority_vote(
                    frame_decisions=frame_decisions
                )

                # Collect class wise probabilities and scale them between [0-1]
                class_probabilities = {}
                for scene_id, scene_label in enumerate(scene_labels):
                    class_probabilities[scene_label] = probabilities[scene_id] / input_data.shape[0]

                res_data = {
                    'filename': db.absolute_to_relative_path(filename),
                    'scene_label': estimated_scene_label
                }
                # Add class class_probabilities
                res_data.update(class_probabilities)

                # Store result into results container
                res.append(
                    res_data
                )

                processed_files.append(filename)

            if not len(res):
                raise ValueError('No results to save.')

            # Save results container
            fields = ['filename', 'scene_label']
            fields += scene_labels

            res.save(fields=fields, csv_header=True)

    return processed_files


def do_evaluation(db, param, log, application_mode='default'):
    """Evaluation stage

    Parameters
    ----------
    db : dcase_util.dataset.Dataset
        Dataset

    param : dcase_util.containers.DCASEAppParameterContainer
        Application parameters

    log : dcase_util.ui.FancyLogger
        Logging interface

    application_mode : str
        Application mode
        Default value 'default'

    Returns
    -------
    nothing

    """

    all_results = []

    devices = [
        'a',
        'b',
        'c',
        's1',
        's2',
        's3',
        's4',
        's5',
        's6'
    ]

    class_wise_results = numpy.zeros((1 + len(devices), len(db.scene_labels())))
    class_wise_results_loss = numpy.zeros((1 + len(devices), len(db.scene_labels())))
    fold = 1

    fold_results_filename = os.path.join(
        param.get_path('path.application.recognizer'),
        'res_fold_{fold}.csv'.format(fold=fold)
    )

    reference_scene_list = db.eval(fold=fold)

    reference_scene_list_devices = {}
    for device in devices:
        reference_scene_list_devices[device] = dcase_util.containers.MetaDataContainer()

    for item_id, item in enumerate(reference_scene_list):
        device = os.path.splitext(os.path.split(item.filename)[-1])[0].split('-')[-1]

        reference_scene_list[item_id]['filename'] = os.path.split(item.filename)[-1]
        reference_scene_list[item_id]['file'] = item.filename

        reference_scene_list_devices[device].append(item)

    estimated_scene_list = dcase_util.containers.MetaDataContainer().load(
        filename=fold_results_filename,
        file_format=dcase_util.utils.FileFormat.CSV,
        csv_header=True,
        delimiter='\t'
    )

    estimated_scene_list_devices = {}
    for device in devices:
        estimated_scene_list_devices[device] = dcase_util.containers.MetaDataContainer()

    for item_id, item in enumerate(estimated_scene_list):
        device = os.path.splitext(os.path.split(item.filename)[-1])[0].split('-')[-1]

        estimated_scene_list[item_id]['filename'] = os.path.split(item.filename)[-1]
        estimated_scene_list[item_id]['file'] = item.filename

        estimated_scene_list_devices[device].append(item)

    evaluator = sed_eval.scene.SceneClassificationMetrics(
        scene_labels=db.scene_labels()
    )

    evaluator.evaluate(
        reference_scene_list=reference_scene_list,
        estimated_scene_list=estimated_scene_list
    )

    # Collect data for log loss calculation
    y_true = []
    y_pred = []

    y_true_scene = {}
    y_pred_scene = {}

    y_true_device = {}
    y_pred_device = {}

    estimated_scene_items = {}
    for item in estimated_scene_list:
        estimated_scene_items[item.filename] = item

    scene_labels = db.scene_labels()
    for item in reference_scene_list:
        # Find corresponding item from estimated_scene_list
        estimated_item = estimated_scene_items[item.filename]

        # Get class id
        scene_label_id = scene_labels.index(item.scene_label)
        y_true.append(scene_label_id)

        # Get class-wise probabilities in correct order
        item_probabilities = []
        for scene_label in scene_labels:
            item_probabilities.append(estimated_item[scene_label])

        y_pred.append(item_probabilities)

        if item.scene_label not in y_true_scene:
            y_true_scene[item.scene_label] = []
            y_pred_scene[item.scene_label] = []

        y_true_scene[item.scene_label].append(scene_label_id)
        y_pred_scene[item.scene_label].append(item_probabilities)

        if item.source_label not in y_true_device:
            y_true_device[item.source_label] = []
            y_pred_device[item.source_label] = []

        y_true_device[item.source_label].append(scene_label_id)
        y_pred_device[item.source_label].append(item_probabilities)

    from sklearn.metrics import log_loss
    logloss_overall = log_loss(y_true=y_true, y_pred=y_pred)

    logloss_class_wise = {}
    for scene_label in db.scene_labels():
        logloss_class_wise[scene_label] = log_loss(
            y_true=y_true_scene[scene_label],
            y_pred=y_pred_scene[scene_label],
            labels=list(range(len(db.scene_labels())))
        )

    logloss_device_wise = {}
    for device_label in list(y_true_device.keys()):

        logloss_device_wise[device_label] = log_loss(
            y_true=y_true_device[device_label],
            y_pred=y_pred_device[device_label],
            labels=list(range(len(db.scene_labels())))
        )

    for scene_label_id, scene_label in enumerate(db.scene_labels()):

        class_wise_results_loss[0, scene_label_id] = logloss_class_wise[scene_label]

        for device_id, device_label in enumerate(y_true_device.keys()):
            scene_device_idx = [i for i in range(len(y_true_device[device_label])) if y_true_device[device_label][i] == scene_label_id]
            y_true_device_scene = [y_true_device[device_label][i] for i in scene_device_idx]
            y_pred_device_scene = [y_pred_device[device_label][i] for i in scene_device_idx]
            class_wise_results_loss[1 + device_id, scene_label_id] = log_loss(
                y_true=y_true_device_scene,
                y_pred=y_pred_device_scene,
                labels=list(range(len(db.scene_labels())))
            )

    results = evaluator.results()
    all_results.append(results)

    evaluator_devices = {}
    for device in devices:
        evaluator_devices[device] = sed_eval.scene.SceneClassificationMetrics(
            scene_labels=db.scene_labels()
        )

        evaluator_devices[device].evaluate(
            reference_scene_list=reference_scene_list_devices[device],
            estimated_scene_list=estimated_scene_list_devices[device]
        )

        results_device = evaluator_devices[device].results()
        all_results.append(results_device)

    for scene_label_id, scene_label in enumerate(db.scene_labels()):
        class_wise_results[0, scene_label_id] = results['class_wise'][scene_label]['accuracy']['accuracy']

        for device_id, device in enumerate(devices):
            class_wise_results[1 + device_id, scene_label_id] = \
                all_results[1 + device_id]['class_wise'][scene_label]['accuracy']['accuracy']

    overall = [
        results['class_wise_average']['accuracy']['accuracy']
    ]
    for device_id, device in enumerate(devices):
        overall.append(all_results[1 + device_id]['class_wise_average']['accuracy']['accuracy'])

    # Get filename
    filename = 'eval_{parameter_hash}_{application_mode}.yaml'.format(
        parameter_hash=param['_hash'],
        application_mode=application_mode
    )

    # Get current parameters
    current_param = dcase_util.containers.AppParameterContainer(param.get_set(param.active_set()))
    current_param._clean_unused_parameters()

    if current_param.get_path('learner.parameters.compile.optimizer'):
        current_param.set_path('learner.parameters.compile.optimizer', None)

    # Save evaluation information
    dcase_util.containers.DictContainer(
        {
            'application_mode': application_mode,
            'set_id': param.active_set(),
            'class_wise_results': class_wise_results_loss.tolist(),
            'overall_accuracy': overall[0],
            'overall_logloss': logloss_overall,
            'all_results': all_results,
            'classwise_logloss': logloss_class_wise,
            'parameters': current_param
        }
    ).save(
        filename=os.path.join(param.get_path('path.application.evaluator'), filename)
    )

    log.line()
    log.row_reset()

    # Table header
    column_headers = ['Scene', 'Logloss']
    column_widths = [16, 10]
    column_types = ['str20', 'float3']
    column_separators = [True, True]
    for dev_id, device in enumerate(devices):
        column_headers.append(device.upper())
        column_widths.append(8)
        column_types.append('float3')
        if dev_id < len(devices) - 1:
            column_separators.append(False)
        else:
            column_separators.append(True)

    column_headers.append('Accuracy')
    column_widths.append(8)
    column_types.append('float1_percentage')
    column_separators.append(False)

    log.row(
        *column_headers,
        widths=column_widths,
        types=column_types,
        separators=column_separators,
        indent=3
    )
    log.row_sep()

    # Class-wise rows
    for scene_label_id, scene_label in enumerate(db.scene_labels()):
        row_data = [scene_label]
        for id in range(class_wise_results_loss.shape[0]):
            row_data.append(class_wise_results_loss[id, scene_label_id])
        row_data.append(class_wise_results[0,scene_label_id]* 100.0)
        log.row(*row_data)
    log.row_sep()

    # Last row
    column_values = ['Logloss']
    column_values.append(logloss_overall)
    column_types.append('float3')

    for device_label in devices:
        column_values.append(logloss_device_wise[device_label])

    column_values.append(' ')

    log.row(
        *column_values,
        types=column_types
    )

    column_values = ['Accuracy', ' ']
    column_types = ['str20', 'float1_percentage']
    for device_id, device_label in enumerate(devices[0:]):
        column_values.append(numpy.mean(class_wise_results[device_id+1,:])*100)
        column_types.append('float1_percentage')

    column_values.append(numpy.mean(class_wise_results[0, :]) * 100)
    column_types.append('float1_percentage')

    log.row(
        *column_values,
        types=column_types,
    )

    log.line()



def do_model_size_calculation(folds, param, log):
    """Model size calculation stage

    Parameters
    ----------
    db : dcase_util.dataset.Dataset
        Dataset

    folds : list
        List of active folds

    param : dcase_util.containers.DCASEAppParameterContainer
        Application parameters

    log : dcase_util.ui.FancyLogger
        Logging interface

    Returns
    -------
    nothing

    """

    for fold in folds:
        log.line(
            data='Fold [{fold}]'.format(fold=fold),
            indent=2
        )

        # Get model filename
        fold_model_filename = os.path.join(
            param.get_path('path.application.learner'),
            'model.tflite'
        )


        # Load acoustic model
        import nessi
        nessi.get_model_size(fold_model_filename,'tflite')


if __name__ == "__main__":
    sys.exit(main())
