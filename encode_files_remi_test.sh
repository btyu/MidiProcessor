MIDI_DIR=../../data/merged-dataset
TRAIN_LIST=../../processed_data/data_split/merged-dataset.1900359-168921-42230/train_list.txt
VALID_LIST=../../processed_data/data_split/merged-dataset.1900359-168921-42230/valid_list.txt
TEST_LIST=../../processed_data/data_split/merged-dataset.1900359-168921-42230/test_list.txt
OUTPUT_DIR=../../processed_data/merged-dataset/remi.merged-dataset.1900359-168921-42230.reb.song_separate.tokenization

MAX_ENCODING_LENGTH=
MAX_BAR=
NUM_WORKERS=8

python batch_encoding.py $MIDI_DIR \
  --encoding_method REMI \
  --file_list $VALID_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name valid \
  --num_workers $NUM_WORKERS \
  --cut_method successive \
  --normalize_keys \
  --remove_bar_idx \
  --remove_empty_bars


#  --max_encoding_length $MAX_ENCODING_LENGTH \
#  --max_bar $MAX_BAR \


python batch_encoding.py $MIDI_DIR \
  --encoding_method REMI \
  --file_list $TEST_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name test \
  --num_workers $NUM_WORKERS \
  --cut_method successive \
  --normalize_keys \
  --remove_bar_idx \
  --remove_empty_bars


python batch_encoding.py $MIDI_DIR \
  --encoding_method REMI \
  --file_list $TRAIN_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name train \
  --num_workers $NUM_WORKERS \
  --cut_method successive \
  --normalize_keys \
  --remove_bar_idx \
  --remove_empty_bars \
  --dump_dict \
  --fairseq_dict
