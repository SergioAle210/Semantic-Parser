class A {
  let x: integer;
  function get(): integer { return this.x; }
}

class B : A { }

function f(): integer {
  let z: string = 3 * "hola"; // error aritmético
  return "no soy int";        // return incompatible
}

function g() {
  y = 10; // variable no declarada
}

function main(): integer {
  const C: integer; // const sin init
  let a: A = new A();
  a.noExiste = 1;   // miembro inexistente
  let m = 5 % true; // operador % mal tipado
  return 0;
}
