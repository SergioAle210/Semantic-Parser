// Helpers "declarados" en el lenguaje; la implementación real la hace el backend MIPS.
function toString(x: integer): string {
  return "";
}

function printInteger(x: integer): integer { return x; }
function printString(x: string): string { return x; }

// Recursividad: Fibonacci
function fibonacci(n: integer): integer {
  if (n <= 1) {
    return n;
  }
  let a: integer = fibonacci(n - 1);
  let b: integer = fibonacci(n - 2);
  let r: integer = a + b;
  return r;
}

// Función Ackermann
function ackermann(m: integer, n: integer): integer {
  if (m == 0) {
    return n + 1;
  }
  if (n == 0) {
    return ackermann(m - 1, 1);
  }
  let inner: integer = ackermann(m, n - 1);
  let res: integer = ackermann(m - 1, inner);
  return res;
}

// Clase base
class Persona {
  let nombre: string;
  let edad: integer;
  let color: string;

  function constructor(nombre: string, edad: integer) {
    this.nombre = nombre;
    this.edad = edad;
    this.color = "rojo";
  }

  function saludar(): string {
    return "Hola, mi nombre es " + this.nombre;
  }

  function incrementarEdad(anos: integer): string {
    this.edad = this.edad + anos;
    return "Ahora tengo " + toString(this.edad) + " años.";
  }
}

// Clase derivada
class Estudiante : Persona {
  let grado: integer;

  function constructor(nombre: string, edad: integer, grado: integer) {
    // No hay 'super': inicializamos campos heredados directamente
    this.nombre = nombre;
    this.edad = edad;
    this.color = "rojo";
    this.grado = grado;
  }

  function estudiar(): string {
    return this.nombre + " está estudiando en " + toString(this.grado) + " año en la Universidad del Valle de Guatemala (UVG).";
  }

  function promedioNotas(n1: integer, n2: integer, n3: integer, n4: integer, n5: integer, n6: integer): integer {
    let promedio: integer = (n1 + n2 + n3 + n4 + n5 + n6) / 6; // división entera
    return promedio;
  }
}

// Programa principal
let log: string = "";
let fibo: string = "";
let ack: string = "";

let nombre: string = "Sergio";
let sergio: Estudiante = new Estudiante(nombre, 15, 4);

let nombre1: string = "Andre";
let andre: Estudiante = new Estudiante(nombre1, 15, 4);

let nombre2: string = "Rodrigo";
let rodri: Estudiante = new Estudiante(nombre2, 15, 4);

// Cabecera y acciones básicas
log = log + sergio.saludar() + "\n";
log = log + sergio.estudiar() + "\n";
log = log + sergio.incrementarEdad(6) + "\n";

log = log + andre.saludar() + "\n";
log = log + andre.estudiar() + "\n";
log = log + andre.incrementarEdad(7) + "\n";

log = log + rodri.saludar() + "\n";
log = log + rodri.estudiar() + "\n";
log = log + rodri.incrementarEdad(6) + "\n";

// Bucle (solo a log, sin imprimir en caliente)
let i: integer = 1;
while (i <= 12) {
  if ((i % 2) == 0) {
    log = log + toString(i) + " es par\n";
  } else {
    log = log + toString(i) + " es impar\n";
  }
  i = i + 1;
}

// Expresión aritmética (entera)
let resultado: integer = (sergio.edad * 2) + ((5 - 3) / 2);
log = log + "Resultado de la expresión: " + toString(resultado) + "\n";

// Promedio (entero)
let prom: integer = 0;
prom = sergio.promedioNotas(99, 95, 98, 100, 95, 94);
log = log + "Promedio (entero): " + toString(prom) + "\n";

// Prueba: Fibonacci recursivo
log = log + "Prueba: Fibonacci recursivo\n";
printString(log);

let nFib: integer = 20;
let k: integer = 0;
while (k <= nFib) {
  let fk: integer = fibonacci(k);
  fibo = "Fib(" + toString(k) + ") = " + toString(fk) + "\n";
  printString(fibo);
  k = k + 1;
}

printString("Prueba: Ackermann\n");
let m: integer = 0;
while (m <= 3) {
  let n: integer = 0;
  while (n <= 8) {
    let a: integer = ackermann(m, n);
    ack = "A(" + toString(m) + ", " + toString(n) + ") = " + toString(a) + "\n";
    printString(ack);
    n = n + 1;
  }
  m = m + 1;
}

