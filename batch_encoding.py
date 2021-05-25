# Author: Botao Yu


import os
import json
import argparse
from tqdm import tqdm

from midi_processing import MidiProcessor
import data_utils


def main():
    # ToDo: 实现所有args对应功能
    # ToDo: processor的构造函数args分离
    parser = argparse.ArgumentParser()
    parser.add_argument('midi_dir', type=str, default='midi')
    parser.add_argument('--encoding_method', choices=['REMI', 'TS1'])
    parser.add_argument('--file_list', type=str, default=None)
    parser.add_argument('--only_mid', action='store_true')
    parser.add_argument('--output_one_file', action='store_true')
    parser.add_argument('--output_dir', type=str, default='tokenization')
    parser.add_argument('--output_base_name', type=str, default=None)
    parser.add_argument('--output_suffix', type=str, default='.token')
    parser.add_argument('--dump_dict', action='store_true')
    parser.add_argument('--fairseq_dict', action='store_true')
    parser.add_argument('--dump_log', action='store_true')

    parser.add_argument('--max_encoding_length', type=int, default=None)
    parser.add_argument('--max_bar', type=int, default=None)
    parser.add_argument('--cut_method', type=str, default='successive')
    parser.add_argument('--remove_bar_idx', action='store_true')
    parser.add_argument('--track_dict', type=str, default=None)

    args = parser.parse_args()

    # === Process ===
    file_path_list = data_utils.get_file_paths(args.midi_dir, file_list=args.file_list,
                                               suffix='.mid' if args.only_mid else None)
    num_files = len(file_path_list)
    print('Processing %d files...' % num_files)

    if args.track_dict is not None:
        with open(args.track_dict, 'r', encoding='utf-8') as f:
            track_dict = json.load(f)
    else:
        track_dict = None

    pcs = MidiProcessor(encoding_method=args.encoding_method)

    multi_encodings = []

    with tqdm(total=num_files) as pbar:
        for file_path in file_path_list:
            basename = os.path.basename(file_path)
            encodings = pcs.encode_file(file_path,
                                        max_encoding_length=args.max_encoding_length,
                                        max_bar=args.max_bar,
                                        cut_method=args.cut_method,
                                        max_bar_num=None,  # Todo
                                        remove_bar_idx=args.remove_bar_idx,
                                        tracks=None if track_dict is None else track_dict[basename])
            encodings = pcs.convert_token_lists_to_token_str_lists(encodings)
            if args.output_one_file:
                multi_encodings.append(encodings)
            else:
                output_path = os.path.join(args.output_dir, basename + args.output_suffix)
                data_utils.dump_lists(encodings, output_path)

            pbar.update(1)

    if args.output_one_file:
        if args.output_base_name is None:
            if args.file_list is not None:
                output_base_name = os.path.basename(args.file_list)
            else:
                raise ValueError("output_base_name cannot be None.")
        else:
            output_base_name = args.output_base_name
        output_path = os.path.join(args.output_dir, output_base_name + args.output_suffix)
        data_utils.dump_lists(multi_encodings, output_path)

    if args.dump_dict:
        pcs.dump_vocab(os.path.join(args.output_dir, 'dict.txt'), fairseq_dict=args.fairseq_dict)


if __name__ == '__main__':
    main()
