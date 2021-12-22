# Author: Botao Yu

import os
import json
import argparse
import zipfile

from tqdm import tqdm
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from midiprocessor import MidiEncoder, data_utils, midi_utils


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
    parser.add_argument('--num_workers', type=int, default=None)
    parser.add_argument('--one_save', action='store_true')
    parser.add_argument('--save_freq', type=int, default=1024)
    parser.add_argument('--zip', action='store_true')
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
    if args.zip:
        file_path_list = data_utils.get_zip_file_paths(args.midi_dir, zip_obj=None, file_list=args.file_list,
                                                       suffix='.mid' if args.only_mid else None)
    else:
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
        if num_workers is None:
            num_workers = pool._max_workers
        m = multiprocessing.Manager()
        lock = m.Lock()
    else:
        pool = None
        lock = None

    encoder = MidiEncoder(encoding_method=args.encoding_method,
                          key_profile_file=args.key_profile_file, )
    skip_error = not args.no_skip_error

    multi_encodings = []
    output_path = os.path.join(args.output_dir, output_base_name + args.output_suffix)
    if args.output_one_file:
        data_utils.ensure_file_dir_to_save(output_path)
        with open(output_path, 'w', encoding='utf-8'):  # clean the file that may exist
            pass

    try:
        if args.zip:
            if pool is None:
                results = batch_process_zip(encoder, args.midi_dir, file_path_list,  args, track_dict,
                                            skip_error=skip_error, save=not args.output_one_file,
                                            output_path=output_path, lock=lock, single_process=True)
                multi_encodings = results
            else:
                each_length = num_files // num_workers + 1
                batch_file_lists = []

                left = 0
                while True:
                    right = min(num_files, left + each_length)
                    temp_file_list = file_path_list[left: right]
                    batch_file_lists.append(temp_file_list)
                    left = right
                    if left >= num_files:
                        break

                tqdm.write('Start processing using %d processes' % num_workers)
                results = pool.map(batch_process_zip,
                                   [encoder] * num_workers,
                                   [args.midi_dir] * num_workers,
                                   batch_file_lists,
                                   [args] * num_workers,
                                   [track_dict] * num_workers,
                                   [skip_error] * num_workers,
                                   [not args.output_one_file] * num_workers,
                                   [output_path] * num_workers,
                                   [lock] * num_workers,
                                   [False] * num_workers,
                                   range(num_workers))
                for result in results:
                    if result is not None:
                        multi_encodings.extend(result)
        else:  # not zip
            if pool is None:
                results = []
                idx = 0
                for file_path in tqdm(file_path_list):
                    result = process_file(encoder, file_path, args, track_dict,
                                          skip_error=skip_error, save=not args.output_one_file)
                    if result is None:
                        continue
                    if args.output_one_file:
                        results.append(result)
                        idx += 1
                        if not args.one_save and idx >= args.save_freq:
                            data_utils.dump_lists(multi_encodings, output_path,
                                                  no_internal_blanks=args.no_internal_blanks,
                                                  open_mode='a')
                multi_encodings = results
            else:
                with tqdm(total=num_files) as process_bar:
                    left = 0
                    idx = 0
                    while left < num_files:
                        right = min(left + num_workers, num_files)

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
                                idx += 1
                            if not args.one_save and idx >= args.save_freq:
                                data_utils.dump_lists(multi_encodings, output_path,
                                                      no_internal_blanks=args.no_internal_blanks,
                                                      open_mode='a')
                                idx = 0
                                multi_encodings = []

                        process_bar.update(len_batch)

                        left = right
    finally:
        if pool is not None:
            pool.shutdown()
        if args.output_one_file and args.one_save:
            data_utils.dump_lists(multi_encodings, output_path, no_internal_blanks=args.no_internal_blanks)
        if args.dump_dict:
            encoder.vm.dump_vocab(os.path.join(args.output_dir, 'dict.txt'), fairseq_dict=args.fairseq_dict)


def process_file(encoder, file_path, args, track_dict, skip_error=True, save=False):
    basename = os.path.basename(file_path)
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
            encodings = None
        else:
            raise

    if no_error and save:
        output_path = os.path.join(args.output_dir, basename + args.output_suffix)
        data_utils.dump_lists(encodings, output_path, no_internal_blanks=args.no_internal_blanks)

    return encodings


def process_zip(encoder, zip_file_path, file_path, args, track_dict, skip_error=True, save=False, zip_file_obj=None):
    basename = os.path.basename(file_path)
    no_error = True

    close_zip = False
    try:
        if zip_file_obj is None:
            close_zip = True
            zip_file_obj = zipfile.ZipFile(zip_file_path, 'r')
        try:
            with zip_file_obj.open(file_path, 'r') as f:
                midi_obj = midi_utils.load_midi(file=f)
            encodings = encoder.encode_file(file_path,
                                            max_encoding_length=args.max_encoding_length,
                                            max_bar=args.max_bar,
                                            trunc_pos=args.trunc_pos,
                                            cut_method=args.cut_method,
                                            remove_bar_idx=args.remove_bar_idx,
                                            remove_empty_bars=args.remove_empty_bars,
                                            normalize_keys=args.normalize_keys,
                                            tracks=None if track_dict is None else track_dict[basename],
                                            midi_obj=midi_obj)
            encodings = encoder.convert_token_lists_to_token_str_lists(encodings)
        except Exception:
            tqdm.write('Error when encoding %s.' % file_path)
            no_error = False
            if skip_error:
                # import traceback
                # print(traceback.format_exc())
                encodings = None
            else:
                raise
    finally:
        if close_zip and zip_file_obj is not None:
            zip_file_obj.close()

    if no_error and save:
        output_path = os.path.join(args.output_dir, basename + args.output_suffix)
        data_utils.dump_lists(encodings, output_path, no_internal_blanks=args.no_internal_blanks)

    return encodings


def batch_process_zip(encoder, zip_file_path, file_path_list, args, track_dict, skip_error=True,
                      save=False, output_path=None, lock=None, single_process=False, bar_position=0):
    if not args.one_save and not single_process:
        assert lock is not None

    multi_encodings = []
    with zipfile.ZipFile(zip_file_path, 'r') as zip_file_obj:

        idx = 0
        for file_path in tqdm(file_path_list, position=bar_position):
            encodings = process_zip(encoder, None, file_path, args, track_dict, skip_error=skip_error, save=save,
                                    zip_file_obj=zip_file_obj)  # encodings for one song
            if encodings is None:
                continue

            if args.output_one_file:
                multi_encodings.append(encodings)
                idx += 1
                if not args.one_save and idx >= args.save_freq:
                    if single_process:
                        data_utils.dump_lists(multi_encodings, output_path,
                                              no_internal_blanks=args.no_internal_blanks,
                                              open_mode='a')
                    else:
                        with lock:
                            data_utils.dump_lists(multi_encodings, output_path,
                                                  no_internal_blanks=args.no_internal_blanks,
                                                  open_mode='a')
                    idx = 0
                    multi_encodings = []
        if not args.one_save and len(multi_encodings) > 0:
            if single_process:
                data_utils.dump_lists(multi_encodings, output_path,
                                      no_internal_blanks=args.no_internal_blanks,
                                      open_mode='a')
            else:
                with lock:
                    data_utils.dump_lists(multi_encodings, output_path,
                                          no_internal_blanks=args.no_internal_blanks,
                                          open_mode='a')
            multi_encodings = []

    return multi_encodings


if __name__ == '__main__':
    main()
