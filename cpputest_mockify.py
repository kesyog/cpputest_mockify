#!/usr/bin/env python
"""
Utility for generating CppUTest mocks from header files.
"""

from __future__ import print_function

import argparse
import datetime
import os.path
import re
import subprocess
import sys

if sys.version_info < (3, 0, 0):
    # pylint: disable=redefined-builtin,invalid-name,undefined-variable
    input = raw_input

try:
    from shutil import which
except ImportError:

    def which(cmd):
        """
        cheesy version of which. rely on `command` shell builtin:
        https://www.gnu.org/software/bash/manual/bash.html#Bash-Builtins
        """
        try:
            output = subprocess.check_output("command -v {}".format(cmd), shell=True)
            return output.encode()
        except subprocess.CalledProcessError:
            return None


HEADER = """
//! @file
//! @copyright Copyright {year}. All Rights Reserved
//!
//! @details

#include "CppUTest/TestHarness.h"
#include "CppUTestExt/MockSupport.h"

extern "C" {{
#include "{input_file}"
{include_files}
}}\n\n""".lstrip()

VOID_MOCK = """
{signature} {{
  mock().actualCall(__func__){with_parameters};
}}""".lstrip()

NON_VOID_MOCK = """
{signature} {{
  return {return_type}mock().actualCall(__func__){with_parameters}
    .{return_value};
}}""".lstrip()

# The keys in this dict are regexes
KNOWN_INCLUDE_FILES = {
    "bool": "#include <stdbool.h>",  # requires CppUTest 3.8
    r"u?int\d+_t": "#include <stdint.h>",
    "size_t": "#include <stddef.h>",
    "FILE": "#include <stdio.h>",
}


class MockError(Exception):
    """Raised if there was an error while parsing the header file"""

    def __init__(self, value):
        self.value = value
        super(MockError, self).__init__()

    def __str__(self):
        return repr(self.value)


class FunctionParser(object):
    """Parse a single C function declaration and generate a mock using the CppUTest framework"""

    FUNC_REGEX = re.compile(
        r"""^(?:extern\ +)?
                             (?P<return_type>(?:[\w\*]+\s+)+\**)
                             (?P<func_name>\w+)\s*\(
                             (?P<arg_list>[\w\*\s\,\[\]\+\-/\.]+)?
                             \);""",
        re.M | re.X,
    )
    VAR_REGEX = re.compile(
        r"""(?P<type>\w[\s\w]*?)\s*
                             (?:(?P<ptr>\**)\s*|\s+)
                             (?P<name>\w+)$""",
        re.X,
    )
    # FIXME doesn't handle "int * const annoying_parameter"
    # FIXME doesn't handle array parameters like "int annoying_parameter[]"

    # Specifies what return value function and default return value to use for various types
    KNOWN_RETURN_VALUES = {
        "int": "returnIntValueOrDefault(WRITEME)",
        "unsigned int": "returnUnsignedIntValueOrDefault(WRITEME)",
        "long int": "returnLongIntValueOrDefault(WRITEME)",
        "unsigned long int": "returnUnsignedLongIntValueOrDefault(WRITEME)",
        "double": "returnDoubleValueOrDefault(WRITEME)",
        "float": "returnDoubleValueOrDefault(WRITEME)",
        "bool": "returnBoolValueOrDefault(WRITEME)",  # requires CppUTest 3.8
        # custom
        "size_t": "returnUnsignedLongIntValueOrDefault(WRITEME)",
    }

    NATIVE_VARIABLE_TYPES = [
        "char",
        "int",
        "uint8_t",
        "uint16_t",
        "uint32_t",
        "int8_t",
        "int16_t",
        "int32_t",
        "float",
        "double",
        "bool",
        "long",
        "long long",
        "unsigned long",
        "unsigned long long",
        "short",
        "unsigned short",
    ]

    def __init__(self, declaration):
        try:
            self.parse_declaration(declaration)
            self.generate_body()
        except MockError as exception:
            print(exception)
            if self.signature is None:
                self.signature = declaration[:-1]  # chop off semicolon
            self.body = "{}\n{{\n  FIXME\n}}".format(self.signature)

    def __str__(self):
        return self.body

    def __repr__(self):
        return "FunctionParser({})".format(self.signature)

    def parse_declaration(self, declaration):
        """Parse a function declaration and store its constituent parts"""
        match = FunctionParser.FUNC_REGEX.match(declaration)
        if match is None:
            raise MockError("Could not parse function declaration")
        match = match.groupdict()
        # Not sure why re is inserting carriage returns. Let's just delete them.
        if match["arg_list"]:
            match["arg_list"] = match["arg_list"].replace("\r", "")
        self.signature = "{return_type}{func_name}({arg_list})".format(**match)
        # Parse argument list
        self.arg_list = []
        if match["arg_list"] and match["arg_list"].strip() not in ["void", ""]:
            for var in match["arg_list"].split(","):
                var_match = FunctionParser.VAR_REGEX.search(var.strip())
                if var_match is None:
                    raise MockError(
                        'Problem parsing parameter "{}" in "{}"'.format(
                            var.strip(), match["arg_list"].strip()
                        )
                    )
                self.arg_list.append(var_match.groupdict())
        # Parse return type
        if match["return_type"].strip() == "void":
            self.return_type = None
        else:
            self.return_type = match["return_type"].strip()

    def generate_body(self):
        """Generate the body of the mock function"""
        with_parameters = self.gen_param_output()
        if self.return_type is None:
            self.body = VOID_MOCK.format(
                with_parameters=with_parameters, signature=self.signature
            )
        else:
            return_output = self.gen_return_output()
            self.body = NON_VOID_MOCK.format(
                with_parameters=with_parameters,
                signature=self.signature,
                return_value=return_output,
                return_type="(" + self.return_type + ")"
                if self.return_type not in self.NATIVE_VARIABLE_TYPES
                else "",
            )

    def gen_param_output(self):
        """Generate output to handle the function parameters"""
        output = ""
        for arg in self.arg_list:
            output += "\n" + " " * 4
            if arg["ptr"] and arg["type"] != "const char":
                # We can't distinguish between an output parameter and a input pointer parameter
                # Just assume it's an output parameter and add a comment flag for the user to
                # check it.
                output += (
                    '.withOutputParameter("{name}", {name})    '
                    "/* CHECKME: ASSUMED OUTPUT PARAMETER */"
                ).format(name=arg["name"])
            else:
                # Assume input parameters can be handled by withParameter. Worst case, the user
                # can handle the compiler error
                output += '.withParameter("{name}", {name})'.format(name=arg["name"])
        return output

    def gen_return_output(self):
        """Generate output to handle the function return value"""
        if (
            self.return_type.find("const char") == 0
            and self.return_type.count("*") == 1
        ):
            return "returnStringValueOrDefault(WRITEME)"

        if "const" in self.return_type and "*" in self.return_type:
            return "returnConstPointerValueOrDefault(WRITEME)"

        if "*" in self.return_type:
            return "returnPointerValueOrDefault(WRITEME)"

        if self.return_type in self.KNOWN_RETURN_VALUES:
            return self.KNOWN_RETURN_VALUES[self.return_type]

        # Fallback behavior. Flag output type to be checked
        if "unsigned" in self.return_type or "uint" in self.return_type:
            return "returnUnsignedLongIntValueOrDefault(WRITEME)    /* CHECKME */"

        return "returnLongIntValueOrDefault(WRITEME)    /* CHECKME */"


def create_mock(input_filepath, output_folder):
    """Generate cpp mock file in output_folder from the C header file specified by input_filepath"""
    if not input_filepath:
        print("No input file specified")
        return
    if not output_folder:
        print("No output location specified")
        return
    if os.path.isfile(output_folder):
        print("{} already exists as a file".format(output_folder))

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)

    with open(input_filepath) as f_in:
        input_header = f_in.read()

    input_filename = os.path.basename(input_filepath)
    # Only accept header files
    if not input_filename.lower().endswith(".h"):
        print(
            'The provided input file "{}" is not a C header file.'.format(
                input_filepath
            )
        )
        return

    mock_filename = "mock_{}.cpp".format(os.path.splitext(input_filename)[0])
    output_filepath = os.path.join(output_folder, mock_filename)
    if os.path.exists(output_filepath):
        print("'{}' exists, overwrite (y/N)? ".format(output_filepath))
        if input().lower() != "y":
            print('Output file "{}" already exists. Aborting.'.format(output_filepath))
            return
    with open(output_filepath, "w") as f_out:
        includes = ""
        for key, value in KNOWN_INCLUDE_FILES.items():
            if value in includes:
                continue
            if re.search(key, input_header):
                includes += value + "\n"

        now_year = datetime.datetime.now().year
        f_out.write(
            HEADER.format(
                year=now_year,
                input_file=input_filename,
                include_files=includes.rstrip(),
            )
        )

        for match in FunctionParser.FUNC_REGEX.finditer(input_header):
            f_out.write("\n" + str(FunctionParser(match.group(0))) + "\n")

    # with clang-format available, reflow the output file too!
    if which("clang-format --help"):
        print("Running clang-format on {}".format(output_filepath))
        subprocess.check_call(
            "clang-format -style=file -i {}".format(output_filepath), shell=True
        )

    print('Wrote output to "{}"'.format(output_filepath))
    print("Make sure to review output file and search for FIXME, CHECKME, and WRITEME")


def main():
    """Main cli entrance point"""
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="auto-generate CppUTest mock file for a given header file"
    )
    parser.add_argument(
        "input_filepath", help="location of header file to generate mock from"
    )
    parser.add_argument(
        "output_folder", help="directory to put generated mock file",
    )
    args = parser.parse_args()

    create_mock(args.input_filepath, args.output_folder)


if __name__ == "__main__":
    main()
