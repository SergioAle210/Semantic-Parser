import pytest
from helpers import errors_of


def test_string_plus_any_ok():
    src = r"""
    let a: integer = 5;
    let b: string = "x=" + a;
    let c = "hola " + true;
    let d = "arr " + [1,2,3];
    """
    errs = errors_of(src)
    assert errs == []


def test_nested_functions_and_closures_ok():
    src = r"""
    function outer(x: integer): integer {
      let k: integer = 10;
      function inner(y: integer): integer {
        return x + y + k; // captura x y k
      }
      return inner(5);
    }
    """
    errs = errors_of(src)
    assert errs == []


def test_closure_capture_from_block_ok():
    src = r"""
    function f(): integer {
      let base: integer = 3;
      {
        let inc: integer = 2;
        function g(n: integer): integer { return n + base + inc; }
        return g(4);
      }
    }
    """
    errs = errors_of(src)
    assert errs == []


def test_wrong_return_type_err():
    src = r"""
    function f(): integer {
      return "hola";
    }
    """
    errs = errors_of(src)
    assert any("Tipo de return incompatible" in e for e in errs)


def test_arithmetic_type_error():
    src = r"""
    let a: string = "hola";
    let b: integer = 3 * a; // error
    """
    errs = errors_of(src)
    assert any("Operación aritmética requiere numéricos" in e for e in errs)


def test_compare_incompatible_err():
    src = r"""
    let a: string = "s";
    let b: integer = 1;
    let c: boolean = a < b; // error, incompatible
    """
    errs = errors_of(src)
    assert any("Comparación incompatible" in e for e in errs)


def test_const_must_init_err():
    src = r"""
    const A: integer = 1;
    const B: string = "x";
    const C: integer; // error
    """
    errs = errors_of(src)
    assert any("Const 'C' requiere inicialización" in e for e in errs)


def test_switch_types_ok():
    src = r"""
    function main(): integer {
      let x: integer = 2;
      switch (x) {
        case 1: print("uno");
        case 2: print("dos");
        default: print("otro");
      }
      return 0;
    }
    """
    errs = errors_of(src)
    assert errs == []


def test_try_catch_print_any_ok():
    src = r"""
    try {
      let xs: integer[] = [1];
      let v = xs[5];
    } catch (err) {
      print(err); // print(any)
    }
    """
    errs = errors_of(src)
    assert errs == []


def test_class_inheritance_and_methods_ok():
    src = r"""
    class A {
      let n: integer;
      function constructor(n: integer) { this.n = n; }
      function get(): integer { return this.n; }
    }
    class B : A {
      function constructor(n: integer) { this.n = n; }
      function get2(): integer { return this.get(); }
    }
    let b: B = new B(7);
    let k: integer = b.get2();
    """
    errs = errors_of(src)
    assert errs == []


def test_inheritance_field_access_and_method_ok():
    src = r"""
    class Animal {
      let nombre: string;
      function constructor(nombre: string) { this.nombre = nombre; }
      function hablar(): string { return this.nombre + " hace ruido."; }
    }
    class Perro : Animal {
      function constructor(nombre: string) { this.nombre = nombre; }
      function ladrido(): string { return this.nombre + " ladra."; }
    }
    function main(): integer {
      let p: Perro = new Perro("Toby");
      print(p.ladrido());
      print(p.hablar()); // método heredado
      return 0;
    }
    """
    assert errors_of(src) == []


def test_inheritance_assign_to_base_field_in_derived_ctor_ok():
    src = r"""
    class A { let x: integer; }
    class B : A {
      function constructor() {
        this.x = 42; // x heredado
      }
    }
    """
    assert errors_of(src) == []


def test_inheritance_base_not_declared_err():
    src = r"""
    class Hijo : Padre {
      let x: integer;
    }
    """
    errs = errors_of(src)
    assert any("Clase base no declarada: Padre" in e for e in errs)


def test_mod_ok():
    src = r"""
    let a: integer = 5 % 2;
    let b: integer = (10 % 4) + 1;
    """
    assert errors_of(src) == []


def test_mod_type_err():
    src = r"""
    let a: integer = 5 % true; // error
    """
    errs = errors_of(src)
    assert any("%" in e for e in errs)
