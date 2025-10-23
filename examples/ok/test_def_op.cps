// --- Utilidad global ---
function toString(x: integer): string {
  // Stub: no convierte, lo evitamos usando printInteger cuando haga falta.
  return "";
}

// Helpers "declarados" en el lenguaje pero la implementación real la hace el backend MIPS.
function printInteger(x: integer): integer { return x; }
function printString(x: string): string { return x; }

// --- Recursividad: Fibonacci ---
function fibonacci(n: integer): integer {
  if (n <= 1) {
    return n;
  }
  let a: integer = fibonacci(n - 1);
  let b: integer = fibonacci(n - 2);
  let r: integer = a + b;
  return r;
}

// --- Clase base ---
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

// --- Clase derivada ---
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
    return this.nombre + " está estudiando en " + toString(this.grado) + " grado.";
  }

  function promedioNotas(nota1: integer, nota2: integer, nota3: integer): integer {
    let promedio: integer = (nota1 + nota2 + nota3) / 3; // división entera
    return promedio;
  }
}

// --- Programa principal ---
let log: string = "";

let nombre: string = "Sergio";
let juan: Estudiante = new Estudiante(nombre, 15, 3);

// Seguimos armando 'log' por compatibilidad...
log = log + juan.saludar() + "\n";
log = log + juan.estudiar() + "\n";
log = log + juan.incrementarEdad(5) + "\n";

// ...pero AHORA sí imprimimos en consola con los helpers:

// Saludo (no usa toString, así que se imprime bien tal cual):
printString(juan.saludar() + "\n");

// Estudiar: imprimimos el string base + el número con printInteger
printString(juan.nombre + " está estudiando en ");
printInteger(juan.grado);
printString(" grado.\n");

// Edad: tras incrementar, imprimimos el número por separado
// (evitamos depender del toString stub)
printString("Ahora tengo ");
printInteger(juan.edad);
printString(" años.\n");

// Bucle (uso de while por compatibilidad)
let i: integer = 1;
while (i <= 5) {
  if ((i % 2) == 0) {
    // "<i> es par"
    printInteger(i);
    printString(" es par\n");

    log = log + toString(i) + " es par\n";
  } else {
    // "<i> es impar"
    printInteger(i);
    printString(" es impar\n");

    log = log + toString(i) + " es impar\n";
  }
  i = i + 1;
}

// Expresión aritmética (entera)
let resultado: integer = (juan.edad * 2) + ((5 - 3) / 2);

// Mostramos "Resultado de la expresión: 51"
printString("Resultado de la expresión: ");
printInteger(resultado);
printString("\n");

log = log + "Resultado de la expresión: " + toString(resultado) + "\n";

// Ejemplo de promedio (entero)
let prom: integer = 0;
prom = juan.promedioNotas(90, 85, 95);

// Mostramos "Promedio (entero): 90"
printString("Promedio (entero): ");
printInteger(prom);
printString("\n");

log = log + "Promedio (entero): " + toString(prom) + "\n";

// --- Prueba: Fibonacci recursivo ---
printString("Prueba: Fibonacci recursivo\n");
let nFib: integer = 10;
let k: integer = 0;
while (k <= nFib) {
  printString("Fib(");
  printInteger(k);
  printString(") = ");
  let fk: integer = fibonacci(k);
  printInteger(fk);
  printString("\n");
  k = k + 1;
}

// Nota: 'log' sigue conteniendo todas las salidas "lógicas", pero
