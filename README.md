# Low Complexity Acoustic Scene Classification
-------------------------------------

Author:
**Chukwuebuka Olisaemeka**, *Anglia Ruskin University* 
[Email](mailto:olisaemekaebuka@gmail.com). 
**Lakshmi Babu Saheer**, *Anglia Ruskin University* 
[Email](mailto:lakshmi.babu-saheer@aru.ac.uk). 


Getting started
===============

1. Clone repository from [Github](https://github.com/marmoi/dcase2021_task1a_baseline).
2. Install requirements with command: `pip install -r requirements.txt`.
3. Extract features from the audio files previously downloaded `python prepare_data.py`.
4. Create a .h5 file with the extracted features. 
   - `python create_h5.py --dataset_file='/TAUUrbanAcousticScenes_2022_Mobile_DevelopmentSet/meta.csv' --workspace='path'`.   
5. Run the task specific application with default settings for model quantization `python task1.py` or  `./task1.py`


Introduction
============

This is the codebase for our entry in the Low-Complexity Acoustic Scene Classification in Detection and Classification of Acoustic Scenes and Events 2022 (DCASE2022) challenge.
You are permitted to build your own systems by extending this system.

### Data preparation
    |
    ├── task1_features.yaml   # Parameters for the prepare_data.py file
    ├── prepare_data.py       # Code to extract features from 1 second files
    └── create_h5.py          # Code to create the features_all.h5 file


Network Architecture
====================
