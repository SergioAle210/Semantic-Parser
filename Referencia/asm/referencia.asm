; Compiscript x86 (NASM, Intel syntax)
extern printf
extern malloc
extern __concat
section .data
fmt_int db "%d", 10, 0
fmt_str db "%s", 10, 0
str0 db 0
str1 db 114, 111, 106, 111, 0
str2 db 72, 111, 108, 97, 44, 32, 109, 105, 32, 110, 111, 109, 98, 114, 101, 32, 101, 115, 32, 0
str3 db 65, 104, 111, 114, 97, 32, 116, 101, 110, 103, 111, 32, 0
str4 db 32, 97, 195, 177, 111, 115, 46, 0
str5 db 114, 111, 106, 111, 0
str6 db 32, 101, 115, 116, 195, 161, 32, 101, 115, 116, 117, 100, 105, 97, 110, 100, 111, 32, 101, 110, 32, 0
str7 db 32, 103, 114, 97, 100, 111, 46, 0
str8 db 0
str9 db 69, 114, 105, 99, 107, 0
str10 db 92, 110, 0
str11 db 92, 110, 0
str12 db 92, 110, 0
str13 db 32, 101, 115, 32, 112, 97, 114, 92, 110, 0
str14 db 32, 101, 115, 32, 105, 109, 112, 97, 114, 92, 110, 0
str15 db 82, 101, 115, 117, 108, 116, 97, 100, 111, 32, 100, 101, 32, 108, 97, 32, 101, 120, 112, 114, 101, 115, 105, 195, 179, 110, 58, 32, 0
str16 db 92, 110, 0
str17 db 80, 114, 111, 109, 101, 100, 105, 111, 32, 40, 101, 110, 116, 101, 114, 111, 41, 58, 32, 0
str18 db 92, 110, 0
section .text
global __toplevel
toString:
    push ebp
    mov ebp, esp
    mov eax, str0
    mov esp, ebp
    pop ebp
    ret
Persona__constructor:
    push ebp
    mov ebp, esp
    mov eax, dword [ebp+8]
    mov ebx, dword [ebp+12]
    mov dword [eax+0], ebx
    mov eax, dword [ebp+8]
    mov ebx, dword [ebp+16]
    mov dword [eax+4], ebx
    mov eax, dword [ebp+8]
    mov dword [eax+8], str1
    mov esp, ebp
    pop ebp
    ret
Persona__saludar:
    push ebp
    mov ebp, esp
    sub esp, 8
    mov eax, dword [ebp+8]
    mov ebx, dword [eax+0]
    mov dword [ebp-4], ebx
    mov eax, dword [ebp-4]
    push eax
    push str2
    call __concat
    add esp, 8
    mov dword [ebp-8], eax
    mov eax, dword [ebp-8]
    mov esp, ebp
    pop ebp
    ret
Persona__incrementarEdad:
    push ebp
    mov ebp, esp
    sub esp, 16
    mov eax, dword [ebp+8]
    mov ebx, dword [eax+4]
    mov dword [ebp-4], ebx
    mov eax, dword [ebp-4]
    mov ebx, dword [ebp+12]
    add eax, ebx
    mov dword [ebp-8], eax
    mov eax, dword [ebp+8]
    mov ebx, dword [ebp-8]
    mov dword [eax+4], ebx
    mov eax, dword [ebp+8]
    mov ebx, dword [eax+4]
    mov dword [ebp-4], ebx
    mov eax, dword [ebp-4]
    push eax
    call toString
    add esp, 4
    mov dword [ebp-12], eax
    mov eax, dword [ebp-12]
    push eax
    push str3
    call __concat
    add esp, 8
    mov dword [ebp-16], eax
    push str4
    mov eax, dword [ebp-16]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-12], eax
    mov eax, dword [ebp-12]
    mov esp, ebp
    pop ebp
    ret
Estudiante__constructor:
    push ebp
    mov ebp, esp
    mov eax, dword [ebp+8]
    mov ebx, dword [ebp+12]
    mov dword [eax+0], ebx
    mov eax, dword [ebp+8]
    mov ebx, dword [ebp+16]
    mov dword [eax+4], ebx
    mov eax, dword [ebp+8]
    mov dword [eax+8], str5
    mov eax, dword [ebp+8]
    mov ebx, dword [ebp+20]
    mov dword [eax+12], ebx
    mov esp, ebp
    pop ebp
    ret
Estudiante__estudiar:
    push ebp
    mov ebp, esp
    sub esp, 16
    mov eax, dword [ebp+8]
    mov ebx, dword [eax+0]
    mov dword [ebp-4], ebx
    push str6
    mov eax, dword [ebp-4]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-8], eax
    mov eax, dword [ebp+8]
    mov ebx, dword [eax+12]
    mov dword [ebp-4], ebx
    mov eax, dword [ebp-4]
    push eax
    call toString
    add esp, 4
    mov dword [ebp-12], eax
    mov eax, dword [ebp-12]
    push eax
    mov eax, dword [ebp-8]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-16], eax
    push str7
    mov eax, dword [ebp-16]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-12], eax
    mov eax, dword [ebp-12]
    mov esp, ebp
    pop ebp
    ret
Estudiante__promedioNotas:
    push ebp
    mov ebp, esp
    sub esp, 12
    mov eax, dword [ebp+12]
    mov ebx, dword [ebp+16]
    add eax, ebx
    mov dword [ebp-8], eax
    mov eax, dword [ebp-8]
    mov ebx, dword [ebp+20]
    add eax, ebx
    mov dword [ebp-12], eax
    mov eax, dword [ebp-12]
    mov ebx, 3
    cdq
    idiv ebx
    mov dword [ebp-8], eax
    mov eax, dword [ebp-8]
    mov dword [ebp-4], eax
    mov eax, dword [ebp-4]
    mov esp, ebp
    pop ebp
    ret
__toplevel:
    push ebp
    mov ebp, esp
    sub esp, 76
    mov eax, str8
    mov dword [ebp-4], eax
    mov eax, str9
    mov dword [ebp-8], eax
    push 16
    call malloc
    add esp, 4
    mov dword [ebp-28], eax
    push 3
    push 20
    mov eax, dword [ebp-8]
    push eax
    mov eax, dword [ebp-28]
    push eax
    call Estudiante__constructor
    add esp, 16
    mov eax, dword [ebp-28]
    mov dword [ebp-12], eax
    mov eax, dword [ebp-12]
    push eax
    call Persona__saludar
    add esp, 4
    mov dword [ebp-32], eax
    mov eax, dword [ebp-32]
    push eax
    mov eax, dword [ebp-4]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-36], eax
    push str10
    mov eax, dword [ebp-36]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-32], eax
    mov eax, dword [ebp-32]
    mov dword [ebp-4], eax
    mov eax, dword [ebp-12]
    push eax
    call Estudiante__estudiar
    add esp, 4
    mov dword [ebp-36], eax
    mov eax, dword [ebp-36]
    push eax
    mov eax, dword [ebp-4]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-40], eax
    push str11
    mov eax, dword [ebp-40]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-36], eax
    mov eax, dword [ebp-36]
    mov dword [ebp-4], eax
    push 5
    mov eax, dword [ebp-12]
    push eax
    call Persona__incrementarEdad
    add esp, 8
    mov dword [ebp-40], eax
    mov eax, dword [ebp-40]
    push eax
    mov eax, dword [ebp-4]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-44], eax
    push str12
    mov eax, dword [ebp-44]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-40], eax
    mov eax, dword [ebp-40]
    mov dword [ebp-4], eax
    mov eax, 1
    mov dword [ebp-16], eax
L0:
    mov eax, dword [ebp-16]
    cmp eax, 5
    jle L1
    jmp L2
L1:
    mov eax, dword [ebp-16]
    mov ebx, 2
    cdq
    idiv ebx
    mov eax, edx
    mov dword [ebp-44], eax
    mov eax, dword [ebp-44]
    cmp eax, 0
    je L3
    jmp L5
L3:
    mov eax, dword [ebp-16]
    push eax
    call toString
    add esp, 4
    mov dword [ebp-44], eax
    mov eax, dword [ebp-44]
    push eax
    mov eax, dword [ebp-4]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-48], eax
    push str13
    mov eax, dword [ebp-48]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-44], eax
    mov eax, dword [ebp-44]
    mov dword [ebp-4], eax
    jmp L4
L5:
    mov eax, dword [ebp-16]
    push eax
    call toString
    add esp, 4
    mov dword [ebp-48], eax
    mov eax, dword [ebp-48]
    push eax
    mov eax, dword [ebp-4]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-52], eax
    push str14
    mov eax, dword [ebp-52]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-48], eax
    mov eax, dword [ebp-48]
    mov dword [ebp-4], eax
L4:
    mov eax, dword [ebp-16]
    mov ebx, 1
    add eax, ebx
    mov dword [ebp-52], eax
    mov eax, dword [ebp-52]
    mov dword [ebp-16], eax
    jmp L0
L2:
    mov eax, dword [ebp-12]
    mov ebx, dword [eax+4]
    mov dword [ebp-56], ebx
    mov eax, dword [ebp-56]
    mov ebx, 2
    imul eax, ebx
    mov dword [ebp-60], eax
    mov eax, 5
    mov ebx, 3
    sub eax, ebx
    mov dword [ebp-56], eax
    mov eax, dword [ebp-56]
    mov ebx, 2
    cdq
    idiv ebx
    mov dword [ebp-64], eax
    mov eax, dword [ebp-60]
    mov ebx, dword [ebp-64]
    add eax, ebx
    mov dword [ebp-56], eax
    mov eax, dword [ebp-56]
    mov dword [ebp-20], eax
    push str15
    mov eax, dword [ebp-4]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-64], eax
    mov eax, dword [ebp-20]
    push eax
    call toString
    add esp, 4
    mov dword [ebp-60], eax
    mov eax, dword [ebp-60]
    push eax
    mov eax, dword [ebp-64]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-68], eax
    push str16
    mov eax, dword [ebp-68]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-60], eax
    mov eax, dword [ebp-60]
    mov dword [ebp-4], eax
    mov eax, 0
    mov dword [ebp-24], eax
    push 95
    push 85
    push 90
    mov eax, dword [ebp-12]
    push eax
    call Estudiante__promedioNotas
    add esp, 16
    mov dword [ebp-68], eax
    mov eax, dword [ebp-68]
    mov dword [ebp-24], eax
    push str17
    mov eax, dword [ebp-4]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-64], eax
    mov eax, dword [ebp-24]
    push eax
    call toString
    add esp, 4
    mov dword [ebp-72], eax
    mov eax, dword [ebp-72]
    push eax
    mov eax, dword [ebp-64]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-76], eax
    push str18
    mov eax, dword [ebp-76]
    push eax
    call __concat
    add esp, 8
    mov dword [ebp-72], eax
    mov eax, dword [ebp-72]
    mov dword [ebp-4], eax
    mov esp, ebp
    pop ebp
    ret