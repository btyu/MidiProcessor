MIDI_DIR=../../data/LMD/lmd_full
TRAIN_LIST=../../processed_data/data_split/lmd_full.160705-14285-3571/train_list.txt
VALID_LIST=../../processed_data/data_split/lmd_full.160705-14285-3571/valid_list.txt
TEST_LIST=../../processed_data/data_split/lmd_full.160705-14285-3571/test_list.txt
OUTPUT_DIR=../../processed_data/lmd_full/remi.lmd_full.160705-14285-3571.reb.song_separate.tokenization

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
  --normalize_keys \
  --remove_bar_idx \
  --remove_empty_bars


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
