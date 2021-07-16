# Author: Botao Yu


import os
import json
import argparse
from tqdm import tqdm
from concurrent.futures import ProcessPoolExecutor

from midi_encoding import MidiEncoder
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
    parser.add_argument('--output_suffix', type=str, default='')
    parser.add_argument('--no_internal_blanks', action='store_true')
    parser.add_argument('--no_skip_error', action='store_true')
    parser.add_argument('--dump_dict', action='store_true')
    parser.add_argument('--fairseq_dict', action='store_true')
    parser.add_argument('--num_workers', type=int, default=1)
    parser.add_argument('--dump_log', action='store_true')  # Todo

    parser.add_argument('--max_encoding_length', type=int, default=None)
    parser.add_argument('--max_bar', type=int, default=None)
    parser.add_argument('--trunc_pos', type=int, default=None)
    parser.add_argument('--cut_method', type=str, default='successive')
    parser.add_argument('--remove_bar_idx', action='store_true')
    parser.add_argument('--remove_empty_bars', action='store_true')
    parser.add_argument('--normalize_keys', action='store_true')
    parser.add_argument('--key_profile_file', type=str, default=None)
    parser.add_argument('--track_dict', type=str, default=None)

    args = parser.parse_args()

    output_base_name = 'default'
    if args.output_one_file:
        if args.output_base_name is None:
            if args.file_list is not None:
                output_base_name = os.path.basename(args.file_list)
            else:
                raise ValueError("output_base_name cannot be None.")
        else:
            output_base_name = args.output_base_name

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

    num_workers = args.num_workers
    assert num_workers >= 1
    if num_workers > 1:
        pool = ProcessPoolExecutor(max_workers=num_workers)
    else:
        pool = None

    encoder = MidiEncoder(encoding_method=args.encoding_method,
                          key_profile_file=args.key_profile_file, )
    skip_error = not args.no_skip_error

    multi_encodings = []

    left = 0
    len_batch = 1

    try:
        with tqdm(total=num_files) as process_bar:
            while left < num_files:
                right = min(left + num_workers, num_files)

                if pool is None:
                    results = process_file(encoder, file_path_list[left], args, track_dict,
                                           skip_error=skip_error, save=not args.output_one_file)
                    results = [results]
                else:
                    batch_files = file_path_list[left: right]
                    len_batch = right - left

                    results = pool.map(process_file,
                                       [encoder] * len_batch,
                                       batch_files,
                                       [args] * len_batch,
                                       [track_dict] * len_batch,
                                       [skip_error] * len_batch,
                                       [not args.output_one_file] * len_batch)

                if args.output_one_file:
                    for result in results:
                        if result is None:
                            continue
                        multi_encodings.append(result)

                process_bar.update(len_batch)

                left = right
    finally:
        if args.output_one_file:
            output_path = os.path.join(args.output_dir, output_base_name + args.output_suffix)
            data_utils.dump_lists(multi_encodings, output_path, no_internal_blanks=args.no_internal_blanks)
        if args.dump_dict:
            encoder.vm.dump_vocab(os.path.join(args.output_dir, 'dict.txt'), fairseq_dict=args.fairseq_dict)


def process_file(encoder, file_path, args, track_dict, skip_error=True, save=False):
    basename = os.path.basename(file_path)
    encodings = None
    no_error = True
    try:
        encodings = encoder.encode_file(file_path,
                                        max_encoding_length=args.max_encoding_length,
                                        max_bar=args.max_bar,
                                        trunc_pos=args.trunc_pos,
                                        cut_method=args.cut_method,
                                        remove_bar_idx=args.remove_bar_idx,
                                        remove_empty_bars=args.remove_empty_bars,
                                        normalize_keys=args.normalize_keys,
                                        tracks=None if track_dict is None else track_dict[basename])
        encodings = encoder.convert_token_lists_to_token_str_lists(encodings)
    except Exception:
        tqdm.write('Error when encoding %s.' % file_path)
        no_error = False
        if skip_error:
            import traceback
            tqdm.write(traceback.format_exc())
        else:
            raise

    if no_error and save:
        output_path = os.path.join(args.output_dir, basename + args.output_suffix)
        data_utils.dump_lists(encodings, output_path, no_internal_blanks=args.no_internal_blanks)

    return encodings


if __name__ == '__main__':
    main()
