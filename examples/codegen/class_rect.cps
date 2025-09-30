class Rect {
  let w: integer;
  let h: integer;

  function constructor(w: integer, h: integer): void {
    this.w = w;
    this.h = h;
  }

  function area(): integer {
    return this.w * this.h;
  }

  function grow(): void {
    this.w = this.w + 1;
  }
}

function main(): integer {
  let r: Rect = Rect(3, 4);   // constructor
  print(r.area());            // 12
  r.grow();
  print(r.area());            // 16
  return 0;
}
