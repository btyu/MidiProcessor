# Author: Botao Yu

import basic_encoding_utils
import cut_utils

TS1_CUT_METHOD = ('successive', 'cut')


def convert_ts1_token_to_token_str(token):
    return basic_encoding_utils.convert_basic_token_to_token_str(token)


def convert_ts1_token_list_to_token_str_list(token_list):
    return basic_encoding_utils.convert_basic_token_list_to_token_str_list(token_list)


def convert_ts1_token_lists_to_token_str_lists(token_lists):
    return basic_encoding_utils.convert_basic_token_lists_to_token_str_lists(token_lists)


def convert_ts1_token_str_to_token(token_str):
    return basic_encoding_utils.convert_basic_token_str_to_token(token_str)


def convert_pos_info_to_ts1_token_lists(pos_to_info,

                                        bar_abbr,
                                        pos_abbr,
                                        pitch_abbr,
                                        duration_abbr,

                                        max_encoding_length=None,
                                        max_bar=None,
                                        cut_method='successive',
                                        max_bar_num=None,
                                        remove_bar_idx=False,
                                        ):
    # bar, pos, pitch, duration

    encoding = []

    max_pos = len(pos_to_info)
    cur_bar = None
    for pos in range(max_pos):
        now_bar, now_ts, now_local_pos, now_tempo, now_insts_notes = pos_to_info[pos]

        cur_local_pos = now_local_pos

        if cur_bar != now_bar:
            cur_bar = now_bar
            encoding.append((bar_abbr, cur_bar))  # bar

        if now_insts_notes is not None:
            cur_insts_notes = now_insts_notes
            encoding.append((pos_abbr, cur_local_pos))  # local pos
            insts_ids = sorted(list(cur_insts_notes.keys()))
            for inst_id in insts_ids:
                inst_notes = sorted(cur_insts_notes[inst_id])
                for pitch, duration, velocity, pos_end in inst_notes:
                    encoding.append((pitch_abbr, pitch))  # pitch
                    encoding.append((duration_abbr, duration))  # duration

    token_lists = cut_ts1_full_token_list(encoding,
                                          bar_abbr,
                                          max_encoding_length=max_encoding_length,
                                          max_bar=max_bar,
                                          cut_method=cut_method,
                                          max_bar_num=max_bar_num,
                                          remove_bar_idx=remove_bar_idx,
                                          )

    return token_lists


def cut_ts1_full_token_list(encoding,
                            bar_abbr,
                            max_encoding_length=None,
                            max_bar=None,
                            cut_method='successive',
                            max_bar_num=None,
                            remove_bar_idx=False,
                            ):

    len_encoding = len(encoding)

    direct_returns = (
        max_encoding_length is None and max_bar is None,
        max_encoding_length is not None and len_encoding <= max_encoding_length and max_bar is None,
        cut_method is None,
    )

    if any(direct_returns):
        return [encoding[:]]

    ts1_check_cut_method(cut_method)

    def get_bar_offset(token_list):  # 获取第一个bar的下标
        for idx, item in enumerate(token_list):
            if item[0] == bar_abbr:
                return idx, item[1]
        return None, None

    def authorize_right(token_list, idx):  # 右边
        return token_list[idx][0] == bar_abbr

    def authorize_bar(encoding, start, pos, offset, max_bar):
        if pos < len(encoding) and encoding[pos][0] == bar_abbr:
            return encoding[pos][1] - offset <= max_bar
        pos -= 1
        while pos >= start:
            if encoding[pos][0] == bar_abbr:
                return encoding[pos][1] - offset < max_bar
            pos -= 1
        raise ValueError("No authorized bar in the encoding range.")

    if cut_method == 'successive':
        return cut_utils.encoding_successive_cut(
            encoding,
            bar_abbr,
            max_length=max_encoding_length,
            max_bar=max_bar,
            get_bar_offset=get_bar_offset,
            authorize_right=authorize_right,
            authorize_bar=authorize_bar,
            len_encoding=len_encoding,
            max_bar_num=max_bar_num,
            remove_bar_idx=remove_bar_idx,
        )
    elif cut_method == 'first':
        return cut_utils.encoding_successive_cut(
            encoding,
            bar_abbr,
            max_length=max_encoding_length,
            max_bar=max_bar,
            get_bar_offset=get_bar_offset,
            authorize_right=authorize_right,
            authorize_bar=authorize_bar,
            len_encoding=max_encoding_length,
            max_bar_num=max_bar_num,
            remove_bar_idx=remove_bar_idx,
        )
    else:
        raise ValueError("Cut method \"%s\" is not currently supported." % cut_method)


def ts1_check_cut_method(cut_method):
    assert cut_method in TS1_CUT_METHOD, "Cut method \"%s\" not in the supported: %s" % \
                                         (cut_method, ', '.join(TS1_CUT_METHOD))
