from Parser import Parser


class CodeWriter:
    SEGMENT_POINTERS = {
        "local": "LCL",
        "argument": "ARG",
        "this": "THIS",
        "that": "THAT",
    }
    POINTER_NAMES = {0: "THIS", 1: "THAT"}

    def __init__(self, output_file):
        self.file = open(output_file, "w")
        self.file_name = ""
        self.current_function = ""
        self.label_counter = 0

    def set_file_name(self, file_name):
        """Called once per .vm file; used to name static variables."""
        self.file_name = file_name

    def close(self):
        self.file.close()

    def _w(self, text):
        self.file.write(text)

    def _new_id(self):
        self.label_counter += 1
        return self.label_counter

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------
    def write_init(self):
        self._w("// Bootstrap code\n")
        self._w("@256\nD=A\n@SP\nM=D\n")
        self.write_call("Sys.init", 0)

    # ------------------------------------------------------------------
    # Arithmetic / logic
    # ------------------------------------------------------------------
    def write_arithmetic(self, command):
        self._w(f"// {command}\n")
        if command in ("add", "sub", "and", "or"):
            op = {"add": "M=D+M", "sub": "M=M-D", "and": "M=D&M", "or": "M=D|M"}[command]
            self._w("@SP\nAM=M-1\nD=M\n@SP\nAM=M-1\n")
            self._w(f"{op}\n@SP\nM=M+1\n")
        elif command in ("neg", "not"):
            op = "M=-M" if command == "neg" else "M=!M"
            self._w(f"@SP\nA=M-1\n{op}\n")
        elif command == "eq":
            self._write_eq()
        elif command in ("gt", "lt"):
            self._write_gt_lt(command)
        else:
            raise ValueError(f"Unknown arithmetic command: {command}")

    def _push_bool_and_finish(self, i):
        """Shared tail for comparisons: (FALSE) push 0, (TRUE) push -1."""
        self._w(f"(CMP_FALSE_{i})\n@SP\nA=M\nM=0\n@CMP_END_{i}\n0;JMP\n")
        self._w(f"(CMP_TRUE_{i})\n@SP\nA=M\nM=-1\n")
        self._w(f"(CMP_END_{i})\n@SP\nM=M+1\n")

    def _write_eq(self):
        i = self._new_id()
        # D = x - y (equality is safe even if the subtraction wraps around)
        self._w("@SP\nAM=M-1\nD=M\n@SP\nAM=M-1\nD=M-D\n")
        self._w(f"@CMP_TRUE_{i}\nD;JEQ\n")
        self._push_bool_and_finish(i)

    def _write_gt_lt(self, command):
        """
        gt/lt compare signs first, because x - y can overflow 16 bits when
        x and y have different signs (e.g. 32767 - (-1)).
        """
        i = self._new_id()
        # When the signs differ, the answer depends only on the sign of x:
        #   gt: x >= 0 (y < 0) -> true ; x < 0 (y >= 0) -> false
        #   lt: x >= 0 (y < 0) -> false; x < 0 (y >= 0) -> true
        x_pos_label = f"CMP_TRUE_{i}" if command == "gt" else f"CMP_FALSE_{i}"
        x_neg_label = f"CMP_FALSE_{i}" if command == "gt" else f"CMP_TRUE_{i}"
        same_jump = "JGT" if command == "gt" else "JLT"

        self._w("@SP\nAM=M-1\nD=M\n@R13\nM=D\n")   # R13 = y
        self._w("@SP\nAM=M-1\nD=M\n@R14\nM=D\n")   # R14 = x
        self._w(f"@CMP_XNEG_{i}\nD;JLT\n")          # x < 0 ?
        # x >= 0
        self._w(f"@R13\nD=M\n@{x_pos_label}\nD;JLT\n")   # y < 0 -> signs differ
        self._w(f"@CMP_SAME_{i}\n0;JMP\n")
        # x < 0
        self._w(f"(CMP_XNEG_{i})\n@R13\nD=M\n@{x_neg_label}\nD;JGE\n")  # y >= 0 -> signs differ
        # same signs: subtraction cannot overflow
        self._w(f"(CMP_SAME_{i})\n@R14\nD=M\n@R13\nD=D-M\n@CMP_TRUE_{i}\nD;{same_jump}\n")
        self._push_bool_and_finish(i)

    # ------------------------------------------------------------------
    # Push / pop
    # ------------------------------------------------------------------
    def write_push_pop(self, command, segment, index):
        if command == Parser.C_PUSH:
            self._w(f"// push {segment} {index}\n")
            self._write_push(segment, index)
        elif command == Parser.C_POP:
            self._w(f"// pop {segment} {index}\n")
            self._write_pop(segment, index)
        else:
            raise ValueError(f"Not a push/pop command: {command}")

    _PUSH_D = "@SP\nA=M\nM=D\n@SP\nM=M+1\n"   # push the value held in D

    def _write_push(self, segment, index):
        if segment == "constant":
            self._w(f"@{index}\nD=A\n")
        elif segment in self.SEGMENT_POINTERS:
            self._w(f"@{self.SEGMENT_POINTERS[segment]}\nD=M\n@{index}\nA=D+A\nD=M\n")
        elif segment == "temp":
            self._w(f"@{5 + index}\nD=M\n")
        elif segment == "pointer":
            self._w(f"@{self.POINTER_NAMES[index]}\nD=M\n")
        elif segment == "static":
            self._w(f"@{self.file_name}.{index}\nD=M\n")
        else:
            raise ValueError(f"Unknown segment: {segment}")
        self._w(self._PUSH_D)

    def _write_pop(self, segment, index):
        if segment in self.SEGMENT_POINTERS:
            # R13 = target address, then store popped value there
            self._w(f"@{self.SEGMENT_POINTERS[segment]}\nD=M\n@{index}\nD=D+A\n@R13\nM=D\n")
            self._w("@SP\nAM=M-1\nD=M\n@R13\nA=M\nM=D\n")
            return
        if segment == "temp":
            target = f"{5 + index}"
        elif segment == "pointer":
            target = self.POINTER_NAMES[index]
        elif segment == "static":
            target = f"{self.file_name}.{index}"
        else:
            raise ValueError(f"Cannot pop to segment: {segment}")
        self._w(f"@SP\nAM=M-1\nD=M\n@{target}\nM=D\n")

    # ------------------------------------------------------------------
    # Branching (labels are scoped to the current function)
    # ------------------------------------------------------------------
    def _scoped(self, label):
        if self.current_function:
            return f"{self.current_function}${label}"
        return label

    def write_label(self, label):
        self._w(f"({self._scoped(label)})\n")

    def write_goto(self, label):
        self._w(f"@{self._scoped(label)}\n0;JMP\n")

    def write_if(self, label):
        self._w(f"@SP\nAM=M-1\nD=M\n@{self._scoped(label)}\nD;JNE\n")

    # ------------------------------------------------------------------
    # Functions
    # ------------------------------------------------------------------
    def write_function(self, function_name, num_locals):
        self.current_function = function_name
        self._w(f"// function {function_name} {num_locals}\n({function_name})\n")
        for _ in range(num_locals):
            self._w("@SP\nA=M\nM=0\n@SP\nM=M+1\n")

    def write_call(self, function_name, num_args):
        return_label = f"{function_name}$ret.{self._new_id()}"
        self._w(f"// call {function_name} {num_args}\n")
        # push return address
        self._w(f"@{return_label}\nD=A\n{self._PUSH_D}")
        # push LCL, ARG, THIS, THAT
        for seg in ("LCL", "ARG", "THIS", "THAT"):
            self._w(f"@{seg}\nD=M\n{self._PUSH_D}")
        # ARG = SP - 5 - num_args
        self._w(f"@SP\nD=M\n@{num_args + 5}\nD=D-A\n@ARG\nM=D\n")
        # LCL = SP
        self._w("@SP\nD=M\n@LCL\nM=D\n")
        # goto function (raw label, not scoped)
        self._w(f"@{function_name}\n0;JMP\n")
        self._w(f"({return_label})\n")

    def write_return(self):
        self._w("// return\n")
        # R13 = FRAME = LCL
        self._w("@LCL\nD=M\n@R13\nM=D\n")
        # R14 = RET = *(FRAME-5)  (saved before *ARG is overwritten)
        self._w("@5\nA=D-A\nD=M\n@R14\nM=D\n")
        # *ARG = pop()
        self._w("@SP\nAM=M-1\nD=M\n@ARG\nA=M\nM=D\n")
        # SP = ARG + 1
        self._w("@ARG\nD=M+1\n@SP\nM=D\n")
        # restore THAT, THIS, ARG, LCL
        for offset, seg in enumerate(("THAT", "THIS", "ARG", "LCL"), 1):
            self._w(f"@R13\nD=M\n@{offset}\nA=D-A\nD=M\n@{seg}\nM=D\n")
        # goto RET
        self._w("@R14\nA=M\n0;JMP\n")