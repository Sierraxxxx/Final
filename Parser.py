class Parser:
    # Command types
    C_ARITHMETIC = "C_ARITHMETIC"
    C_PUSH = "C_PUSH"
    C_POP = "C_POP"
    C_LABEL = "C_LABEL"
    C_GOTO = "C_GOTO"
    C_IF = "C_IF"
    C_FUNCTION = "C_FUNCTION"
    C_RETURN = "C_RETURN"
    C_CALL = "C_CALL"

    ARITHMETIC = ["add", "sub", "neg", "eq", "gt", "lt", "and", "or", "not"]
    COMMANDS = {
        "push": C_PUSH,
        "pop": C_POP,
        "label": C_LABEL,
        "goto": C_GOTO,
        "if-goto": C_IF,
        "function": C_FUNCTION,
        "return": C_RETURN,
        "call": C_CALL,
    }

    def __init__(self, input_file):
        with open(input_file, "r") as file:
            self.lines = file.readlines()
        self.current_command = []
        self.current_line_index = -1

    def has_more_lines(self):
        """True if there are lines left to read."""
        return self.current_line_index + 1 < len(self.lines)

    def advance(self):
        """Reads the next real command, skipping blank lines and comments."""
        self.current_command = []
        while self.has_more_lines():
            self.current_line_index += 1
            line = self.lines[self.current_line_index].split("//")[0].strip()
            if line:
                self.current_command = line.split()
                return

    def command_type(self):
        cmd = self.current_command[0]
        if cmd in self.ARITHMETIC:
            return self.C_ARITHMETIC
        if cmd in self.COMMANDS:
            return self.COMMANDS[cmd]
        raise ValueError(
            f"Unknown command '{cmd}' on line {self.current_line_index + 1}"
        )

    def arg1(self):
        if self.command_type() == self.C_ARITHMETIC:
            return self.current_command[0]
        return self.current_command[1]

    def arg2(self):
        return int(self.current_command[2])