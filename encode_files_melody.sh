MIDI_DIR=../../data/LMD/lmd_ts_10k
TRAIN_LIST=../../data/data_split/lmd_ts_10k/train_list.json
VALID_LIST=../../data/data_split/lmd_ts_10k/valid_list.json
TEST_LIST=../../data/data_split/lmd_ts_10k/test_list.json
OUTPUT_DIR=../../data/new_all_remi/melody_tokenization
TRACK_DICT=../../data/LMD/main_melody_info/melody_midi_dict.json

MAX_ENCODING_LENGTH=1022
MAX_BAR=256

python batch_encoding.py $MIDI_DIR \
  --file_list $VALID_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name valid \
  --max_encoding_length $MAX_ENCODING_LENGTH \
  --max_bar $MAX_BAR \
  --cut_method successive \
  --remove_bar_idx \
  --no_internal_blanks \
  --track_dict $TRACK_DICT

python batch_encoding.py $MIDI_DIR \
  --file_list $TEST_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name test \
  --max_encoding_length $MAX_ENCODING_LENGTH \
  --max_bar $MAX_BAR \
  --cut_method successive \
  --remove_bar_idx \
  --no_internal_blanks \
  --track_dict $TRACK_DICT


python batch_encoding.py $MIDI_DIR \
  --file_list $TRAIN_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name train \
  --dump_dict \
  --fairseq_dict \
  --max_encoding_length $MAX_ENCODING_LENGTH \
  --max_bar $MAX_BAR \
  --cut_method successive \
  --remove_bar_idx \
  --no_internal_blanks \
  --track_dict $TRACK_DICT
