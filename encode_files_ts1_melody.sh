MIDI_DIR=../../data/LMD/lmd_ts_10k
TRAIN_LIST=../../processed_data/data_split/lmd_ts_10k/train_list.json
VALID_LIST=../../processed_data/data_split/lmd_ts_10k/valid_list.json
TEST_LIST=../../processed_data/data_split/lmd_ts_10k/test_list.json
OUTPUT_DIR=../../processed_data/lmd_ts_10k/ts1_new_melody_successive_1022_256_tokenization
TRACK_DICT=../../data/LMD/main_melody_info/melody_midi_dict.json

MAX_ENCODING_LENGTH=1022
MAX_BAR=256
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
  --no_internal_blanks \
  --remove_bar_idx \
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
  --no_internal_blanks \
  --remove_bar_idx \
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
  --no_internal_blanks \
  --remove_bar_idx \
  --track_dict $TRACK_DICT \
  --dump_dict \
  --fairseq_dict
