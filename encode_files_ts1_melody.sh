MIDI_DIR=../../data/LMD/lmd_melody
TRAIN_LIST=../../processed_data/data_split/lmd_melody_99245-8822-2205/train_list.txt
VALID_LIST=../../processed_data/data_split/lmd_melody_99245-8822-2205/valid_list.txt
TEST_LIST=../../processed_data/data_split/lmd_melody_99245-8822-2205/test_list.txt
OUTPUT_DIR=../../processed_data/lmd_melody/ts1.lmd_melody.99245_8822_2205.melody_track.reb.tokenization
TRACK_DICT=../../data/LMD/main_melody_info/melody_midi_dict.json

MAX_ENCODING_LENGTH=20000000
MAX_BAR=20000000
NUM_WORKERS=64

python batch_encoding.py $MIDI_DIR \
  --encoding_method TS1 \
  --file_list $VALID_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name valid \
  --num_workers $NUM_WORKERS \
  --max_encoding_length $MAX_ENCODING_LENGTH \
  --max_bar $MAX_BAR \
  --cut_method successive \
  --key_profile_file key_profile.pickle \
  --normalize_keys \
  --no_internal_blanks \
  --remove_bar_idx \
  --remove_empty_bars \
  --track_dict $TRACK_DICT


python batch_encoding.py $MIDI_DIR \
  --encoding_method TS1 \
  --file_list $TEST_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name test \
  --num_workers $NUM_WORKERS \
  --max_encoding_length $MAX_ENCODING_LENGTH \
  --max_bar $MAX_BAR \
  --cut_method successive \
  --key_profile_file key_profile.pickle \
  --normalize_keys \
  --no_internal_blanks \
  --remove_bar_idx \
  --remove_empty_bars \
  --track_dict $TRACK_DICT


python batch_encoding.py $MIDI_DIR \
  --encoding_method TS1 \
  --file_list $TRAIN_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name train \
  --num_workers $NUM_WORKERS \
  --max_encoding_length $MAX_ENCODING_LENGTH \
  --max_bar $MAX_BAR \
  --cut_method successive \
  --key_profile_file key_profile.pickle \
  --normalize_keys \
  --no_internal_blanks \
  --remove_bar_idx \
  --remove_empty_bars \
  --track_dict $TRACK_DICT \
  --dump_dict \
  --fairseq_dict
