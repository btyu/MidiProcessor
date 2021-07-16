MIDI_DIR=../../data/kunstderfuge-com_complete_collection
TRAIN_LIST=../../processed_data/data_split/kunstderfuge_clean.15237_1354_339/train_list.txt
VALID_LIST=../../processed_data/data_split/kunstderfuge_clean.15237_1354_339/valid_list.txt
TEST_LIST=../../processed_data/data_split/kunstderfuge_clean.15237_1354_339/test_list.txt
OUTPUT_DIR=../../processed_data/kunstderfuge/kunstderfuge_clean.15237_1354_339.melody_track.reb.l4000.tokenization
TRACK_DICT=../../processed_data/kunstderfuge/info_note/melody_midi_dict.json

MAX_ENCODING_LENGTH=4000
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
