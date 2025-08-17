class A {
  let n: integer;
  function constructor(n: integer) {this.n = n;}
  function get(): integer { return this.n; }
}
print(123);           // int
print(3 / 2);         // float
print(true);          // bool
print("hola");        // string
let xs: integer[] = [1, 2];
print(xs);            // array(int)
let a: A = new A(7);
print(a);             
