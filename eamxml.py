import argparse
import lxml.etree as etree

try:
    from ctypes import *
    import codecs

    libeamxml = cdll.LoadLibrary("libeamxml.dll")
    libeamxml.get_raw_xml.restype = c_char_p
    libeamxml.get_binxml.restype = POINTER(c_byte)

    def get_raw_xml(input):
        try:
            output = libeamxml.get_raw_xml(bytes(input), len(input))
            output = bytes(output.decode("Shift-JIS"), 'shift-jis')
            root = etree.fromstring(output)
            return etree.tostring(root, encoding='unicode', pretty_print=True)
        except:
            return ""

    def get_binxml(input):
        input = input.encode("shift-jis")
        output_size = c_int()
        return bytearray(string_at(libeamxml.get_binxml(input, len(input), byref(output_size)), output_size.value))
except:
    try:
        from kbinxml import KBinXML

        def get_raw_xml(input):
            try:
                output = KBinXML(input).to_text()
                root = etree.fromstring(output.encode('utf-8'))
                return etree.tostring(root, encoding='unicode', pretty_print=True)
            except:
                return ""

        def get_binxml(input):
            return KBinXML(input.encode('utf-8')).to_binary()
    except:
        print("Couldn't load any code to handle binary XML files")
        exit(1)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-e', '--encode', action='store_true', help='Encode mode')
    group.add_argument('-d', '--decode', action='store_true', help='Decode mode')
    parser.add_argument('-i', '--input', help='Input file', required=True)
    parser.add_argument('-o', '--output', help='Output file', required=True)
    args = parser.parse_args()

    data = open(args.input, "rb").read()

    if args.encode:
        output = get_binxml(data.decode('utf-8'))
    else:
        output = bytearray(get_raw_xml(data), encoding="utf-8")

    open(args.output, "wb").write(output)

    print("Finished writing data to {}!".format(args.output))