
artifacts/ths-analysis-20261016/deep/tonghuashun-arm64:	file format mach-o arm64

Disassembly of section __TEXT,__text:

000000010000375c <__text>:
1004cc8a8: a9bd57f6    	stp	x22, x21, [sp, #-0x30]!
1004cc8ac: a9014ff4    	stp	x20, x19, [sp, #0x10]
1004cc8b0: a9027bfd    	stp	x29, x30, [sp, #0x20]
1004cc8b4: 910083fd    	add	x29, sp, #0x20
1004cc8b8: aa0203f5    	mov	x21, x2
1004cc8bc: aa0103f3    	mov	x19, x1
1004cc8c0: aa0003f4    	mov	x20, x0
1004cc8c4: 39800008    	ldrsb	x8, [x0]
1004cc8c8: 39400409    	ldrb	w9, [x0, #0x1]
1004cc8cc: d370bd08    	lsl	x8, x8, #16
1004cc8d0: aa092108    	orr	x8, x8, x9, lsl #8
1004cc8d4: 39400809    	ldrb	w9, [x0, #0x2]
1004cc8d8: aa090108    	orr	x8, x8, x9
1004cc8dc: 39400c09    	ldrb	w9, [x0, #0x3]
1004cc8e0: aa082136    	orr	x22, x9, x8, lsl #8
1004cc8e4: d2c00028    	mov	x8, #0x100000000        ; =4294967296
1004cc8e8: 8b168108    	add	x8, x8, x22, lsl #32
1004cc8ec: 9360fd09    	asr	x9, x8, #32
1004cc8f0: f100011f    	cmp	x8, #0x0
1004cc8f4: da9fa120    	csinv	x0, x9, xzr, ge
1004cc8f8: 9420ff8c    	bl	0x100d0c728 <dyld_stub_binder+0x100d0c728>
1004cc8fc: f90002a0    	str	x0, [x21]
1004cc900: 38404e90    	ldrb	w16, [x20, #0x4]!
1004cc904: 91000a88    	add	x8, x20, #0x2
1004cc908: 3940068a    	ldrb	w10, [x20, #0x1]
1004cc90c: 3900000a    	strb	w10, [x0]
1004cc910: f1000adf    	cmp	x22, #0x2
1004cc914: 54001d6b    	b.lt	0x1004cccc0 <__text+0x4c9564>
1004cc918: 8b160009    	add	x9, x0, x22
1004cc91c: 9100040c    	add	x12, x0, #0x1
1004cc920: 5280010e    	mov	w14, #0x8               ; =8
1004cc924: 528fffeb    	mov	w11, #0x7fff            ; =32767
1004cc928: 510005ce    	sub	w14, w14, #0x1
1004cc92c: 72001ddf    	tst	w14, #0xff
1004cc930: 540001a0    	b.eq	0x1004cc964 <__text+0x4c9208>
1004cc934: 531f7a0d    	lsl	w13, w16, #1
1004cc938: 373801d0    	tbnz	w16, #0x7, 0x1004cc970 <__text+0x4c9214>
1004cc93c: 3940010a    	ldrb	w10, [x8]
1004cc940: aa0c03ef    	mov	x15, x12
1004cc944: 380015ea    	strb	w10, [x15], #0x1
1004cc948: eb0901ff    	cmp	x15, x9
1004cc94c: 54001c48    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004cc950: 3940050a    	ldrb	w10, [x8, #0x1]
1004cc954: 91000908    	add	x8, x8, #0x2
1004cc958: 9100098f    	add	x15, x12, #0x2
1004cc95c: 3900058a    	strb	w10, [x12, #0x1]
1004cc960: 14000046    	b	0x1004cca78 <__text+0x4c931c>
1004cc964: 3840150d    	ldrb	w13, [x8], #0x1
1004cc968: 5280010e    	mov	w14, #0x8               ; =8
1004cc96c: 363ffe90    	tbz	w16, #0x7, 0x1004cc93c <__text+0x4c91e0>
1004cc970: 510005ce    	sub	w14, w14, #0x1
1004cc974: 72001ddf    	tst	w14, #0xff
1004cc978: 540001e0    	b.eq	0x1004cc9b4 <__text+0x4c9258>
1004cc97c: 531f79b0    	lsl	w16, w13, #1
1004cc980: 3738006d    	tbnz	w13, #0x7, 0x1004cc98c <__text+0x4c9230>
1004cc984: 3840150a    	ldrb	w10, [x8], #0x1
1004cc988: 3800158a    	strb	w10, [x12], #0x1
1004cc98c: eb09019f    	cmp	x12, x9
1004cc990: 54001a28    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004cc994: aa0c03ef    	mov	x15, x12
1004cc998: 380015ea    	strb	w10, [x15], #0x1
1004cc99c: 510005ce    	sub	w14, w14, #0x1
1004cc9a0: 72001ddf    	tst	w14, #0xff
1004cc9a4: 54000100    	b.eq	0x1004cc9c4 <__text+0x4c9268>
1004cc9a8: 531f7a0d    	lsl	w13, w16, #1
1004cc9ac: 36380670    	tbz	w16, #0x7, 0x1004cca78 <__text+0x4c931c>
1004cc9b0: 14000008    	b	0x1004cc9d0 <__text+0x4c9274>
1004cc9b4: 38401510    	ldrb	w16, [x8], #0x1
1004cc9b8: 5280010e    	mov	w14, #0x8               ; =8
1004cc9bc: 363ffe4d    	tbz	w13, #0x7, 0x1004cc984 <__text+0x4c9228>
1004cc9c0: 17fffff3    	b	0x1004cc98c <__text+0x4c9230>
1004cc9c4: 3840150d    	ldrb	w13, [x8], #0x1
1004cc9c8: 5280010e    	mov	w14, #0x8               ; =8
1004cc9cc: 36380570    	tbz	w16, #0x7, 0x1004cca78 <__text+0x4c931c>
1004cc9d0: eb0901ff    	cmp	x15, x9
1004cc9d4: 54001808    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004cc9d8: 3900058a    	strb	w10, [x12, #0x1]
1004cc9dc: 510005ce    	sub	w14, w14, #0x1
1004cc9e0: 72001ddf    	tst	w14, #0xff
1004cc9e4: 54000060    	b.eq	0x1004cc9f0 <__text+0x4c9294>
1004cc9e8: 531f79b0    	lsl	w16, w13, #1
1004cc9ec: 14000003    	b	0x1004cc9f8 <__text+0x4c929c>
1004cc9f0: 38401510    	ldrb	w16, [x8], #0x1
1004cc9f4: 5280010e    	mov	w14, #0x8               ; =8
1004cc9f8: 9100098f    	add	x15, x12, #0x2
1004cc9fc: 373800ed    	tbnz	w13, #0x7, 0x1004cca18 <__text+0x4c92bc>
1004cca00: 510005ce    	sub	w14, w14, #0x1
1004cca04: 72001ddf    	tst	w14, #0xff
1004cca08: 54000200    	b.eq	0x1004cca48 <__text+0x4c92ec>
1004cca0c: 531f7a0d    	lsl	w13, w16, #1
1004cca10: 36380350    	tbz	w16, #0x7, 0x1004cca78 <__text+0x4c931c>
1004cca14: 14000010    	b	0x1004cca54 <__text+0x4c92f8>
1004cca18: eb0901ff    	cmp	x15, x9
1004cca1c: 540015c8    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004cca20: 91000d8d    	add	x13, x12, #0x3
1004cca24: 3900098a    	strb	w10, [x12, #0x2]
1004cca28: eb0901bf    	cmp	x13, x9
1004cca2c: 54001548    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004cca30: 39000d8a    	strb	w10, [x12, #0x3]
1004cca34: 510005ce    	sub	w14, w14, #0x1
1004cca38: 72001ddf    	tst	w14, #0xff
1004cca3c: 54000160    	b.eq	0x1004cca68 <__text+0x4c930c>
1004cca40: 531f7a0d    	lsl	w13, w16, #1
1004cca44: 1400000b    	b	0x1004cca70 <__text+0x4c9314>
1004cca48: 3840150d    	ldrb	w13, [x8], #0x1
1004cca4c: 5280010e    	mov	w14, #0x8               ; =8
1004cca50: 36380150    	tbz	w16, #0x7, 0x1004cca78 <__text+0x4c931c>
1004cca54: eb0901ff    	cmp	x15, x9
1004cca58: 540013e8    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004cca5c: 91000d8f    	add	x15, x12, #0x3
1004cca60: 3900098a    	strb	w10, [x12, #0x2]
1004cca64: 14000005    	b	0x1004cca78 <__text+0x4c931c>
1004cca68: 3840150d    	ldrb	w13, [x8], #0x1
1004cca6c: 5280010e    	mov	w14, #0x8               ; =8
1004cca70: 9100118f    	add	x15, x12, #0x4
1004cca74: 373800d0    	tbnz	w16, #0x7, 0x1004cca8c <__text+0x4c9330>
1004cca78: aa0d03f0    	mov	x16, x13
1004cca7c: aa0f03ec    	mov	x12, x15
1004cca80: eb0901ff    	cmp	x15, x9
1004cca84: 54fff523    	b.lo	0x1004cc928 <__text+0x4c91cc>
1004cca88: 1400008e    	b	0x1004cccc0 <__text+0x4c9564>
1004cca8c: eb0901ff    	cmp	x15, x9
1004cca90: 54001228    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004cca94: 3900118a    	strb	w10, [x12, #0x4]
1004cca98: 510005ce    	sub	w14, w14, #0x1
1004cca9c: 72001ddf    	tst	w14, #0xff
1004ccaa0: 54000060    	b.eq	0x1004ccaac <__text+0x4c9350>
1004ccaa4: 531f79b0    	lsl	w16, w13, #1
1004ccaa8: 14000003    	b	0x1004ccab4 <__text+0x4c9358>
1004ccaac: 38401510    	ldrb	w16, [x8], #0x1
1004ccab0: 5280010e    	mov	w14, #0x8               ; =8
1004ccab4: 9100158f    	add	x15, x12, #0x5
1004ccab8: 373800cd    	tbnz	w13, #0x7, 0x1004ccad0 <__text+0x4c9374>
1004ccabc: 510005ce    	sub	w14, w14, #0x1
1004ccac0: 72001ddf    	tst	w14, #0xff
1004ccac4: 540002e0    	b.eq	0x1004ccb20 <__text+0x4c93c4>
1004ccac8: 531f7a11    	lsl	w17, w16, #1
1004ccacc: 14000017    	b	0x1004ccb28 <__text+0x4c93cc>
1004ccad0: eb0901ff    	cmp	x15, x9
1004ccad4: 54001008    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccad8: 9100198d    	add	x13, x12, #0x6
1004ccadc: 3900158a    	strb	w10, [x12, #0x5]
1004ccae0: eb0901bf    	cmp	x13, x9
1004ccae4: 54000f88    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccae8: 91001d8d    	add	x13, x12, #0x7
1004ccaec: 3900198a    	strb	w10, [x12, #0x6]
1004ccaf0: eb0901bf    	cmp	x13, x9
1004ccaf4: 54000f08    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccaf8: 9100218d    	add	x13, x12, #0x8
1004ccafc: 39001d8a    	strb	w10, [x12, #0x7]
1004ccb00: eb0901bf    	cmp	x13, x9
1004ccb04: 54000e88    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccb08: 3900218a    	strb	w10, [x12, #0x8]
1004ccb0c: 510005ce    	sub	w14, w14, #0x1
1004ccb10: 72001ddf    	tst	w14, #0xff
1004ccb14: 540003e0    	b.eq	0x1004ccb90 <__text+0x4c9434>
1004ccb18: 531f7a11    	lsl	w17, w16, #1
1004ccb1c: 1400001f    	b	0x1004ccb98 <__text+0x4c943c>
1004ccb20: 38401511    	ldrb	w17, [x8], #0x1
1004ccb24: 5280010e    	mov	w14, #0x8               ; =8
1004ccb28: 531f7a2d    	lsl	w13, w17, #1
1004ccb2c: 510005ce    	sub	w14, w14, #0x1
1004ccb30: 72001ddf    	tst	w14, #0xff
1004ccb34: 37380150    	tbnz	w16, #0x7, 0x1004ccb5c <__text+0x4c9400>
1004ccb38: 54000061    	b.ne	0x1004ccb44 <__text+0x4c93e8>
1004ccb3c: 3840150d    	ldrb	w13, [x8], #0x1
1004ccb40: 5280010e    	mov	w14, #0x8               ; =8
1004ccb44: 363ff9b1    	tbz	w17, #0x7, 0x1004cca78 <__text+0x4c931c>
1004ccb48: eb0901ff    	cmp	x15, x9
1004ccb4c: 54000c48    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccb50: 9100198f    	add	x15, x12, #0x6
1004ccb54: 3900158a    	strb	w10, [x12, #0x5]
1004ccb58: 17ffffc8    	b	0x1004cca78 <__text+0x4c931c>
1004ccb5c: 54000061    	b.ne	0x1004ccb68 <__text+0x4c940c>
1004ccb60: 3840150d    	ldrb	w13, [x8], #0x1
1004ccb64: 5280010e    	mov	w14, #0x8               ; =8
1004ccb68: eb0901ff    	cmp	x15, x9
1004ccb6c: 373804d1    	tbnz	w17, #0x7, 0x1004ccc04 <__text+0x4c94a8>
1004ccb70: 54000b28    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccb74: 9100198f    	add	x15, x12, #0x6
1004ccb78: 3900158a    	strb	w10, [x12, #0x5]
1004ccb7c: eb0901ff    	cmp	x15, x9
1004ccb80: 54000aa8    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccb84: 91001d8f    	add	x15, x12, #0x7
1004ccb88: 3900198a    	strb	w10, [x12, #0x6]
1004ccb8c: 17ffffbb    	b	0x1004cca78 <__text+0x4c931c>
1004ccb90: 38401511    	ldrb	w17, [x8], #0x1
1004ccb94: 5280010e    	mov	w14, #0x8               ; =8
1004ccb98: 9100258f    	add	x15, x12, #0x9
1004ccb9c: 531f7a2d    	lsl	w13, w17, #1
1004ccba0: 510005ce    	sub	w14, w14, #0x1
1004ccba4: 72001ddf    	tst	w14, #0xff
1004ccba8: 37380150    	tbnz	w16, #0x7, 0x1004ccbd0 <__text+0x4c9474>
1004ccbac: 54000061    	b.ne	0x1004ccbb8 <__text+0x4c945c>
1004ccbb0: 3840150d    	ldrb	w13, [x8], #0x1
1004ccbb4: 5280010e    	mov	w14, #0x8               ; =8
1004ccbb8: 363ff611    	tbz	w17, #0x7, 0x1004cca78 <__text+0x4c931c>
1004ccbbc: eb0901ff    	cmp	x15, x9
1004ccbc0: 540008a8    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccbc4: 9100298f    	add	x15, x12, #0xa
1004ccbc8: 3900258a    	strb	w10, [x12, #0x9]
1004ccbcc: 17ffffab    	b	0x1004cca78 <__text+0x4c931c>
1004ccbd0: 54000061    	b.ne	0x1004ccbdc <__text+0x4c9480>
1004ccbd4: 3840150d    	ldrb	w13, [x8], #0x1
1004ccbd8: 5280010e    	mov	w14, #0x8               ; =8
1004ccbdc: eb0901ff    	cmp	x15, x9
1004ccbe0: 373802b1    	tbnz	w17, #0x7, 0x1004ccc34 <__text+0x4c94d8>
1004ccbe4: 54000788    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccbe8: 9100298f    	add	x15, x12, #0xa
1004ccbec: 3900258a    	strb	w10, [x12, #0x9]
1004ccbf0: eb0901ff    	cmp	x15, x9
1004ccbf4: 54000708    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccbf8: 91002d8f    	add	x15, x12, #0xb
1004ccbfc: 3900298a    	strb	w10, [x12, #0xa]
1004ccc00: 17ffff9e    	b	0x1004cca78 <__text+0x4c931c>
1004ccc04: 54000688    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccc08: 9100198f    	add	x15, x12, #0x6
1004ccc0c: 3900158a    	strb	w10, [x12, #0x5]
1004ccc10: eb0901ff    	cmp	x15, x9
1004ccc14: 54000608    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccc18: 91001d8f    	add	x15, x12, #0x7
1004ccc1c: 3900198a    	strb	w10, [x12, #0x6]
1004ccc20: eb0901ff    	cmp	x15, x9
1004ccc24: 54000588    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccc28: 9100218f    	add	x15, x12, #0x8
1004ccc2c: 39001d8a    	strb	w10, [x12, #0x7]
1004ccc30: 17ffff92    	b	0x1004cca78 <__text+0x4c931c>
1004ccc34: 54000508    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccc38: 9100298f    	add	x15, x12, #0xa
1004ccc3c: 3900258a    	strb	w10, [x12, #0x9]
1004ccc40: eb0901ff    	cmp	x15, x9
1004ccc44: 54000488    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccc48: 91002d8f    	add	x15, x12, #0xb
1004ccc4c: 3900298a    	strb	w10, [x12, #0xa]
1004ccc50: eb0901ff    	cmp	x15, x9
1004ccc54: 54000408    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccc58: 9100318f    	add	x15, x12, #0xc
1004ccc5c: 39002d8a    	strb	w10, [x12, #0xb]
1004ccc60: aa0803f0    	mov	x16, x8
1004ccc64: 38c01611    	ldrsb	w17, [x16], #0x1
1004ccc68: 12001e2c    	and	w12, w17, #0xff
1004ccc6c: 37f80071    	tbnz	w17, #0x1f, 0x1004ccc78 <__text+0x4c951c>
1004ccc70: aa1003e8    	mov	x8, x16
1004ccc74: 14000005    	b	0x1004ccc88 <__text+0x4c952c>
1004ccc78: 39400510    	ldrb	w16, [x8, #0x1]
1004ccc7c: 2a0c220c    	orr	w12, w16, w12, lsl #8
1004ccc80: 91000908    	add	x8, x8, #0x2
1004ccc84: 5140218c    	sub	w12, w12, #0x8, lsl #12 ; =0x8000
1004ccc88: 34ffef8c    	cbz	w12, 0x1004cca78 <__text+0x4c931c>
1004ccc8c: d2800010    	mov	x16, #0x0               ; =0
1004ccc90: 2a0c03ec    	mov	w12, w12
1004ccc94: 8b1001f1    	add	x17, x15, x16
1004ccc98: eb09023f    	cmp	x17, x9
1004ccc9c: 540001c8    	b.hi	0x1004cccd4 <__text+0x4c9578>
1004ccca0: 3900022a    	strb	w10, [x17]
1004ccca4: 91000610    	add	x16, x16, #0x1
1004ccca8: 6b10019f    	cmp	w12, w16
1004cccac: 54ffff41    	b.ne	0x1004ccc94 <__text+0x4c9538>
1004cccb0: 8b1001ef    	add	x15, x15, x16
1004cccb4: 6b0b019f    	cmp	w12, w11
1004cccb8: 54fffd40    	b.eq	0x1004ccc60 <__text+0x4c9504>
1004cccbc: 17ffff6f    	b	0x1004cca78 <__text+0x4c931c>
1004cccc0: 51001269    	sub	w9, w19, #0x4
1004cccc4: 8b29c289    	add	x9, x20, w9, sxtw
1004cccc8: eb09011f    	cmp	x8, x9
1004ccccc: 1a9f02c0    	csel	w0, w22, wzr, eq
1004cccd0: 14000002    	b	0x1004cccd8 <__text+0x4c957c>
1004cccd4: 52800000    	mov	w0, #0x0                ; =0
1004cccd8: a9427bfd    	ldp	x29, x30, [sp, #0x20]
1004cccdc: a9414ff4    	ldp	x20, x19, [sp, #0x10]
1004ccce0: a8c357f6    	ldp	x22, x21, [sp], #0x30
1004ccce4: d65f03c0    	ret
