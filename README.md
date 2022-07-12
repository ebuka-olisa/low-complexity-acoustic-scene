# Low Complexity Acoustic Scene Classification
DCASE2022 - Task 1 A - Baseline systems
-------------------------------------

Author:
**Chukwuebuka Olisaemeka**, *Anglia Ruskin University* 
[Email](mailto:irene.martinmorato@tuni.fi). 
**Lakshmi Babu Saheer**, *Anglia Ruskin University* 


Getting started
===============

1. Clone repository from [Github](https://github.com/marmoi/dcase2021_task1a_baseline).
2. Install requirements with command: `pip install -r requirements.txt`.
3. Extract features from the audio files previously downloaded `python prepare_data.py`.
4. Create a .h5 file with the extracted features. 
   - `python create_h5.py --dataset_file='/TAUUrbanAcousticScenes_2022_Mobile_DevelopmentSet/meta.csv' --workspace='path'`.   
5. Run the task specific application with default settings for model quantization `python task1.py` or  `./task1.py`
