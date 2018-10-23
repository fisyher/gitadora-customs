import json
import os


class JsonFormat:
    @staticmethod
    def get_format_name():
        return "JSON"

    @staticmethod
    def to_json(params):
        input_filename = os.path.join(params.get('input'), "output.json")

        if not input_filename or not os.path.exists(input_filename):
            return None

        with open(input_filename, "rb") as f:
            return f.read()

    @staticmethod
    def to_chart(params):
        output_filename = os.path.join(params.get('output', ""), "output.json")

        with open(output_filename, "w") as f:
            f.write(params.get('input', ""))

    @staticmethod
    def is_format(filename):
        return False


def get_class():
    return JsonFormat
