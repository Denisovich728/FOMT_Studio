# ============================================================
# FOMT Studio - Suite de Ingeniería Inversa (v3.4.4)
# "Actualización La Imposibilidad"
# Desarrollado por: Denisovich728
# ============================================================
from dataclasses import dataclass
from typing import List, Optional
from enum import Enum, auto

# Type Aliases corresponding to Rust's i64 and Vec<u8>
IntValue = int
StrValue = bytes

@dataclass(frozen=True)
class JumpId:
    id: int

@dataclass(frozen=True)
class SwitchId:
    id: int

@dataclass(frozen=True)
class VarId:
    id: int

@dataclass(frozen=True)
class StrId:
    id: int

@dataclass(frozen=True)
class CallId:
    id: int

class ValueTypeEnum(Enum):
    UNDEFINED = auto()
    INTEGER = auto()
    STRING = auto()
    USER_TYPE = auto()

@dataclass
class ValueType:
    type_enum: ValueTypeEnum
    user_type_id: Optional[int] = None
    
    @classmethod
    def undefined(cls): return cls(ValueTypeEnum.UNDEFINED)
    
    @classmethod
    def integer(cls): return cls(ValueTypeEnum.INTEGER)
    
    @classmethod
    def string(cls): return cls(ValueTypeEnum.STRING)
    
    @classmethod
    def user_type(cls, type_id: int): return cls(ValueTypeEnum.USER_TYPE, type_id)

@dataclass
class CallableShape:
    parameter_types: List[ValueType]
    has_return_value: bool

    @classmethod
    def new_func(cls, parameter_types: List[ValueType]):
        return cls(parameter_types, has_return_value=True)

    @classmethod
    def new_proc(cls, parameter_types: List[ValueType]):
        return cls(parameter_types, has_return_value=False)

    def is_func(self) -> bool:
        return self.has_return_value

    def num_parameters(self) -> int:
        return len(self.parameter_types)

class CaseEnum:
    pass

@dataclass(frozen=True)
class CaseVal(CaseEnum):
    val: IntValue

@dataclass(frozen=True)
class CaseDefault(CaseEnum):
    pass

class Ins:
    """Base Instruction class."""
    def branch_target(self) -> Optional[JumpId]:
        return None

    def __eq__(self, other):
        """Instances of the same empty class are equal."""
        if type(self) is type(other):
            return self.__dict__ == other.__dict__
        return False

# Parameterless Instructions
class Assign(Ins): pass
class AssignAdd(Ins): pass
class AssignSub(Ins): pass
class AssignMul(Ins): pass
class AssignDiv(Ins): pass
class AssignMod(Ins): pass
class Add(Ins): pass
class Sub(Ins): pass
class Mul(Ins): pass
class Div(Ins): pass
class Mod(Ins): pass
class LogicalAnd(Ins): pass
class LogicalOr(Ins): pass
class Inc(Ins): pass
class Dec(Ins): pass
class Neg(Ins): pass
class LogicalNot(Ins): pass
class Cmp(Ins): pass
class Dupe(Ins): pass
class Discard(Ins): pass
class Exit(Ins): pass

# Instructions with parameters
@dataclass
class PushVar(Ins):
    var_id: VarId

@dataclass
class PopVar(Ins):
    var_id: VarId

@dataclass
class PushInt(Ins):
    value: IntValue

@dataclass
class Jmp(Ins):
    jump_id: JumpId

# Branch Instructions
@dataclass
class BranchIns(Ins):
    jump_id: JumpId
    def branch_target(self) -> Optional[JumpId]:
        return self.jump_id

class Blt(BranchIns): pass
class Ble(BranchIns): pass
class Beq(BranchIns): pass
class Bne(BranchIns): pass
class Bge(BranchIns): pass
class Bgt(BranchIns): pass

@dataclass
class Call(Ins):
    call_id: CallId

@dataclass
class Switch(Ins):
    switch_id: SwitchId

@dataclass
class Case(Ins):
    switch_id: SwitchId
    case_enum: CaseEnum

@dataclass
class Label(Ins):
    jump_id: JumpId

@dataclass
class Script:
    instructions: List[Ins]
    strings: List[StrValue]
