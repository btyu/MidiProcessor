# Author: Botao Yu


import os
import argparse
import zipfile

from tqdm import tqdm
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

from midiprocessor import MidiEncoder, data_utils, midi_utils
from midiprocessor.midi_encoding import ENCODINGS as ENC_ENCODINGS


def add_args_for_batch_operation(parser):
    parser.add_argument('midi_dir')
    parser.add_argument('--file-list', type=str, default=None)
    parser.add_argument('--midi-suffices', type=lambda x: x.split(','), default=('.mid', '.midi'))
    parser.add_argument('--output-dir', type=str, default='tokenization')
    parser.add_argument('--output-suffix', type=str, default='.txt')
    parser.add_argument('--output-pos-info-id', action='store_true')
    parser.add_argument('--no-skip-error', action='store_true')
    parser.add_argument('--dump-dict', action='store_true')
    parser.add_argument('--fairseq-dict', action='store_true')
    parser.add_argument('--num-workers', type=int, default=None)
    parser.add_argument('--zip', action='store_true')
    # parser.add_argument('--dump_log', action='store_true')


def add_args_for_encoding(parser):
    parser.add_argument('--encoding-method', choices=ENC_ENCODINGS, required=True)
    parser.add_argument('--normalize-pitch-value', action='store_true')
    parser.add_argument('--remove-empty-bars', action='store_true')
    parser.add_argument('--end-offset', type=int, default=0)


def main():
    parser = argparse.ArgumentParser()
    add_args_for_batch_operation(parser)
    add_args_for_encoding(parser)
    args = parser.parse_args()

    # === Process ===
    if args.zip:
        file_path_list = data_utils.get_zip_file_paths(args.midi_dir, zip_obj=None, file_list=args.file_list,
                                                       suffixes=args.midi_suffices)
    else:
        file_path_list = data_utils.get_file_paths(args.midi_dir, file_list=args.file_list,
                                                   suffixes=args.midi_suffices)
    num_files = len(file_path_list)
    print('Processing %d files...' % num_files)

    num_workers = args.num_workers
    if num_workers is None:
        num_workers = multiprocessing.cpu_count()
    assert num_workers >= 1
    if num_workers > 1:
        pool = ProcessPoolExecutor(max_workers=num_workers)
    else:
        pool = None

    encoder = MidiEncoder(
        encoding_method=args.encoding_method,
    )
    skip_error = not args.no_skip_error

    try:
        if args.zip:
            if pool is None:
                batch_process_zip(encoder, args.midi_dir, file_path_list, args, None,
                                  skip_error=skip_error, save=True, need_output=False)
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
                pool.map(
                    batch_process_zip,
                    [encoder] * num_workers,
                    [args.midi_dir] * num_workers,
                    batch_file_lists,
                    [args] * num_workers,
                    [None] * num_workers,
                    [skip_error] * num_workers,
                    [True] * num_workers,
                    [False] * num_workers,
                    range(num_workers)
                )
        else:  # not zip
            if pool is None:
                for file_path in tqdm(file_path_list):
                    _ = process_file(encoder, file_path, args, None,
                                     skip_error=skip_error, save=True)
            else:
                with tqdm(total=num_files) as process_bar:
                    left = 0
                    while left < num_files:
                        right = min(left + num_workers, num_files)

                        batch_files = file_path_list[left: right]
                        len_batch = right - left

                        pool.map(process_file,
                                 [encoder] * len_batch,
                                 batch_files,
                                 [args] * len_batch,
                                 [None] * len_batch,
                                 [skip_error] * len_batch,
                                 [True] * len_batch)

                        process_bar.update(len_batch)
                        left = right
    finally:
        if pool is not None:
            pool.shutdown()
        if args.dump_dict:
            encoder.vm.dump_vocab(os.path.join(args.output_dir, 'dict.txt'), fairseq_dict=args.fairseq_dict)


def process_file(encoder, file_path, args, track_dict, skip_error=True, save=False):
    basename = os.path.basename(file_path)
    no_error = True
    try:
        encodings = encoder.encode_file(
            file_path,
            end_offset=getattr(args, 'end_offset', 0),
            normalize_pitch_value=args.normalize_pitch_value,
            tracks=None if track_dict is None else track_dict[basename],
            save_pos_info_id_path=(None if not getattr(args, 'output_pos_info_id', False)
                                   else os.path.join(args.output_dir, 'pos_info_id', basename + '.json')),
            remove_empty_bars=getattr(args, 'remove_empty_bars', False),
        )
        encodings = encoder.convert_token_lists_to_token_str_lists(encodings)
    except:
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
        data_utils.dump_lists(encodings, output_path, no_internal_blanks=True)

    return encodings


def process_zip(
    encoder,
    zip_file_path,
    file_path,
    args,
    track_dict,
    skip_error=True,
    save=False,
    zip_file_obj=None
):
    raise NotImplementedError("Need to combine the file operations with the standard pipeline.")
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
            encodings = encoder.encode_file(
                file_path,
                tracks=None if track_dict is None else track_dict[basename],
                midi_obj=midi_obj
            )
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
        data_utils.dump_lists(encodings, output_path, no_internal_blanks=True)

    return encodings


def batch_process_zip(encoder, zip_file_path, file_path_list, args, track_dict, skip_error=True,
                      save=False, need_output=False, bar_position=0):
    multi_encodings = []
    with zipfile.ZipFile(zip_file_path, 'r') as zip_file_obj:
        for file_path in tqdm(file_path_list, position=bar_position):
            encodings = process_zip(encoder, None, file_path, args, track_dict, skip_error=skip_error, save=save,
                                    zip_file_obj=zip_file_obj)  # encodings for one song
            if need_output:
                multi_encodings.append(encodings)
    if need_output:
        return multi_encodings
    return None


if __name__ == '__main__':
    main()
