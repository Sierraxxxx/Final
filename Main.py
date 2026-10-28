import os
import sys

from CodeWriter import CodeWriter
from Parser import Parser


def collect_input(input_path):
    """Returns (list of .vm files, output .asm path, whether to emit bootstrap)."""
    input_path = os.path.abspath(input_path)

    if os.path.isdir(input_path):
        vm_files = sorted(
            os.path.join(input_path, f)
            for f in os.listdir(input_path)
            if f.endswith(".vm")
        )
        dir_name = os.path.basename(input_path)
        output_file = os.path.join(input_path, f"{dir_name}.asm")
        # Bootstrap only makes sense when the program has a Sys.init
        needs_bootstrap = os.path.exists(os.path.join(input_path, "Sys.vm"))
    elif os.path.isfile(input_path) and input_path.endswith(".vm"):
        vm_files = [input_path]
        output_file = input_path[:-3] + ".asm"
        needs_bootstrap = False
    else:
        raise SystemExit("Provide a .vm file or a directory containing .vm files.")

    if not vm_files:
        raise SystemExit("No .vm files found.")
    return vm_files, output_file, needs_bootstrap


def translate_file(parser, writer):
    while parser.has_more_lines():
        parser.advance()
        if not parser.current_command:
            continue

        cmd_type = parser.command_type()

        if cmd_type == Parser.C_ARITHMETIC:
            writer.write_arithmetic(parser.arg1())
        elif cmd_type in (Parser.C_PUSH, Parser.C_POP):
            writer.write_push_pop(cmd_type, parser.arg1(), parser.arg2())
        elif cmd_type == Parser.C_LABEL:
            writer.write_label(parser.arg1())
        elif cmd_type == Parser.C_GOTO:
            writer.write_goto(parser.arg1())
        elif cmd_type == Parser.C_IF:
            writer.write_if(parser.arg1())
        elif cmd_type == Parser.C_FUNCTION:
            writer.write_function(parser.arg1(), parser.arg2())
        elif cmd_type == Parser.C_CALL:
            writer.write_call(parser.arg1(), parser.arg2())
        elif cmd_type == Parser.C_RETURN:
            writer.write_return()


def translate(input_path):
    vm_files, output_file, needs_bootstrap = collect_input(input_path)

    writer = CodeWriter(output_file)
    try:
        if needs_bootstrap:
            writer.write_init()

        for vm_file in vm_files:
            writer.set_file_name(os.path.splitext(os.path.basename(vm_file))[0])
            translate_file(Parser(vm_file), writer)
    finally:
        writer.close()

    print(f"Translated: {output_file}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python Main.py <file.vm | directory>")
    else:
        translate(sys.argv[1])