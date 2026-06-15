
    .thumb
    .syntax unified
    hook:
      push {r3, r4}
      ldr r3, =0x04000000
      ldrh r4, [r3]
      movs r3, #0x80
      lsls r3, r3, #3
      tst r4, r3
      beq use_bg1
    use_bg2:
      adds r1, #0x1A
      b done
    use_bg1:
      adds r1, #0x18
    done:
      lsls r1, r1, #0xb
      adds r1, r1, r6
      mov r0, ip
      pop {r3, r4}
      ldr r2, =0x0806EE05
      bx r2
    .align 2
    .pool
    