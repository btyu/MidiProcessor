# Author: Botao Yu

from . import enc_basic_utils


def convert_remi_token_to_token_str(token):
    return enc_basic_utils.convert_basic_token_to_token_str(token)


def convert_remi_token_list_to_token_str_list(token_list):
    return enc_basic_utils.convert_basic_token_list_to_token_str_list(token_list)


def convert_remi_token_lists_to_token_str_lists(token_lists):
    return enc_basic_utils.convert_basic_token_lists_to_token_str_lists(token_lists)


def convert_remi_token_str_to_token(token_str):
    return enc_basic_utils.convert_basic_token_str_to_token(token_str)


def convert_remi_token_str_list_to_token_list(token_str_list):
    return enc_basic_utils.convert_basic_token_str_list_to_token_list(token_str_list)
