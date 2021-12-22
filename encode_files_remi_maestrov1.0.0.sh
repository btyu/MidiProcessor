MIDI_DIR=../../data/maestro-v1.0.0
TRAIN_LIST=$MIDI_DIR/train_list.txt
VALID_LIST=$MIDI_DIR/valid_list.txt
TEST_LIST=$MIDI_DIR/test_list.txt
OUTPUT_DIR=../../processed_data/maestro-v1.0.0/remi.maestro-v1.tokenization

MAX_ENCODING_LENGTH=None
MAX_BAR=200000000000000
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
  --remove_bar_idx


python batch_encoding.py $MIDI_DIR \
  --encoding_method REMI \
  --file_list $TEST_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name test \
  --num_workers $NUM_WORKERS \
  --cut_method successive \
  --remove_bar_idx


python batch_encoding.py $MIDI_DIR \
  --encoding_method REMI \
  --file_list $TRAIN_LIST \
  --only_mid \
  --output_one_file \
  --output_dir $OUTPUT_DIR \
  --output_base_name train \
  --num_workers $NUM_WORKERS \
  --cut_method successive \
  --remove_bar_idx \
  --dump_dict \
  --fairseq_dict
