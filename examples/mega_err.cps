// Const sin inicializar
const K: integer;

// Incompatibilidades de tipos
let x: integer = "hola";
let b: boolean = 5;

// Arreglo heterogéneo
let arr: integer[] = [1, true];

// Índice no-integer
let z = arr["0"];

// foreach sobre no-arreglo
foreach (e in 123) {
  print(e);
}

// Condiciones no boolean
if (5) {
  print("no");
} else {
  print("si");
}
while ("x") {
  print("loop");
}

// for con condición no boolean
for (let i: integer = 0; "x"; i = i + 1) {
}

// break/continue fuera de bucle
break;
continue;

// return fuera de función
return 5;

// Return de tipo inválido + código muerto después del return
function f(a: integer, b: integer): integer {
  return "s";
  print("muerto");
}

// break dentro de función, sin bucle
function g(): integer {
  break;
  return 0;
}

// Clase: asignación a miembro inexistente en el constructor
class A {
  let n: integer;
  function constructor(n: integer) { this.m = n; }
  function get(): integer { return this.n; }
}

// new con tipo de argumento incorrecto
let a: A = new A("X");

// Miembro inexistente
let t = a.missing;

// Indexar un no-arreglo
let xi: integer = 5;
let bad = xi[0];

// Llamar “método” sobre no-clase
arr.hablar();

// switch/case incompatibles
let x2: integer = 0;
switch (x2) {
  case true:
    print("bad");
}

// 'this' fuera de método de clase
function oops(): integer {
  this.nombre = "x";
  return 0;
}

// Aridad incorrecta en llamada
function suma(a: integer, b: integer): integer { return a + b; }
let addRes: integer = suma(1);

// Redeclaración en el mismo ámbito
let dupe: integer;
let dupe: string;

// Función duplicada
function dup(): integer { return 1; }
function dup(): integer { return 2; }

// Uso de variable no declarada
y = 1;
