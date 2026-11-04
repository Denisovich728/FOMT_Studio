#include <stdint.h>
#include <stddef.h>

#define ROTRIGHT(a,b) (((a) >> (b)) | ((a) << (32-(b))))
#define CH(x,y,z) (((x) & (y)) ^ (~(x) & (z)))
#define MAJ(x,y,z) (((x) & (y)) ^ ((x) & (z)) ^ ((y) & (z)))
#define EP0(x) (ROTRIGHT(x,2) ^ ROTRIGHT(x,13) ^ ROTRIGHT(x,22))
#define EP1(x) (ROTRIGHT(x,6) ^ ROTRIGHT(x,11) ^ ROTRIGHT(x,25))
#define SIG0(x) (ROTRIGHT(x,7) ^ ROTRIGHT(x,18) ^ ((x) >> 3))
#define SIG1(x) (ROTRIGHT(x,17) ^ ROTRIGHT(x,19) ^ ((x) >> 10))

typedef struct {
    uint8_t data[64];
    uint32_t datalen;
    unsigned long long bitlen;
    uint32_t state[8];
} SHA256_CTX;

static const uint32_t k[64] = {
    0x428a2f98,0x71374491,0xb5c0fbcf,0xe9b5dba5,0x3956c25b,0x59f111f1,0x923f82a4,0xab1c5ed5,
    0xd807aa98,0x12835b01,0x243185be,0x550c7dc3,0x72be5d74,0x80deb1fe,0x9bdc06a7,0xc19bf174,
    0xe49b69c1,0xefbe4786,0x0fc19dc6,0x240ca1cc,0x2de92c6f,0x4a7484aa,0x5cb0a9dc,0x76f988da,
    0x983e5152,0xa831c66d,0xb00327c8,0xbf597fc7,0xc6e00bf3,0xd5a79147,0x06ca6351,0x14292967,
    0x27b70a85,0x2e1b2138,0x4d2c6dfc,0x53380d13,0x650a7354,0x766a0abb,0x81c2c92e,0x92722c85,
    0xa2bfe8a1,0xa81a664b,0xc24b8b70,0xc76c51a3,0xd192e819,0xd6990624,0xf40e3585,0x106aa070,
    0x19a4c116,0x1e376c08,0x2748774c,0x34b0bcb5,0x391c0cb3,0x4ed8aa4a,0x5b9cca4f,0x682e6ff3,
    0x748f82ee,0x78a5636f,0x84c87814,0x8cc70208,0x90befffa,0xa4506ceb,0xbef9a3f7,0xc67178f2
};

static void sha256_transform(SHA256_CTX *ctx, const uint8_t data[]) {
    uint32_t a, b, c, d, e, f, g, h, i, j, t1, t2, m[64];
    for (i = 0, j = 0; i < 16; ++i, j += 4)
        m[i] = (data[j] << 24) | (data[j + 1] << 16) | (data[j + 2] << 8) | (data[j + 3]);
    for ( ; i < 64; ++i)
        m[i] = SIG1(m[i - 2]) + m[i - 7] + SIG0(m[i - 15]) + m[i - 16];
    a = ctx->state[0]; b = ctx->state[1]; c = ctx->state[2]; d = ctx->state[3];
    e = ctx->state[4]; f = ctx->state[5]; g = ctx->state[6]; h = ctx->state[7];
    for (i = 0; i < 64; ++i) {
        t1 = h + EP1(e) + CH(e,f,g) + k[i] + m[i];
        t2 = EP0(a) + MAJ(a,b,c);
        h = g; g = f; f = e; e = d + t1;
        d = c; c = b; b = a; a = t1 + t2;
    }
    ctx->state[0] += a; ctx->state[1] += b; ctx->state[2] += c; ctx->state[3] += d;
    ctx->state[4] += e; ctx->state[5] += f; ctx->state[6] += g; ctx->state[7] += h;
}

static void sha256_init(SHA256_CTX *ctx) {
    ctx->datalen = 0;
    ctx->bitlen = 0;
    ctx->state[0] = 0x6a09e667; ctx->state[1] = 0xbb67ae85;
    ctx->state[2] = 0x3c6ef372; ctx->state[3] = 0xa54ff53a;
    ctx->state[4] = 0x510e527f; ctx->state[5] = 0x9b05688c;
    ctx->state[6] = 0x1f83d9ab; ctx->state[7] = 0x5be0cd19;
}

static void sha256_update(SHA256_CTX *ctx, const uint8_t data[], size_t len) {
    for (size_t i = 0; i < len; ++i) {
        ctx->data[ctx->datalen] = data[i];
        ctx->datalen++;
        if (ctx->datalen == 64) {
            sha256_transform(ctx, ctx->data);
            ctx->bitlen += 512;
            ctx->datalen = 0;
        }
    }
}

static void sha256_final(SHA256_CTX *ctx, uint8_t hash[]) {
    uint32_t i = ctx->datalen;
    if (ctx->datalen < 56) {
        ctx->data[i++] = 0x80;
        while (i < 56) ctx->data[i++] = 0x00;
    } else {
        ctx->data[i++] = 0x80;
        while (i < 64) ctx->data[i++] = 0x00;
        sha256_transform(ctx, ctx->data);
        for (int k = 0; k < 56; k++) ctx->data[k] = 0;
    }
    ctx->bitlen += ctx->datalen * 8;
    ctx->data[63] = ctx->bitlen;
    ctx->data[62] = ctx->bitlen >> 8;
    ctx->data[61] = ctx->bitlen >> 16;
    ctx->data[60] = ctx->bitlen >> 24;
    ctx->data[59] = ctx->bitlen >> 32;
    ctx->data[58] = ctx->bitlen >> 40;
    ctx->data[57] = ctx->bitlen >> 48;
    ctx->data[56] = ctx->bitlen >> 56;
    sha256_transform(ctx, ctx->data);
    for (i = 0; i < 4; ++i) {
        hash[i]      = (ctx->state[0] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 4]  = (ctx->state[1] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 8]  = (ctx->state[2] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 12] = (ctx->state[3] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 16] = (ctx->state[4] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 20] = (ctx->state[5] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 24] = (ctx->state[6] >> (24 - i * 8)) & 0x000000ff;
        hash[i + 28] = (ctx->state[7] >> (24 - i * 8)) & 0x000000ff;
    }
}

// ============================================================
//  DESENMASCARAMIENTO DE ALTA ENTROPIA (CHAOS STREAM)
// ============================================================

static void unmask_buffer(const uint8_t *src, uint8_t *dst, size_t len, const uint8_t *seed, size_t seed_len) {
    size_t stream_pos = 0;
    uint32_t counter = 0;
    uint8_t hash[32];
    SHA256_CTX ctx;

    while (stream_pos < len) {
        sha256_init(&ctx);
        sha256_update(&ctx, seed, seed_len);
        sha256_update(&ctx, (const uint8_t *)&counter, 4);
        sha256_final(&ctx, hash);
        counter++;

        for (size_t i = 0; i < 32 && stream_pos < len; ++i) {
            dst[stream_pos] = src[stream_pos] ^ hash[i];
            stream_pos++;
        }
    }
}

// Inclusiones de arrays de bytes de alta entropia (cero texto plano en el binario)
#include "c_arrays.inc"

// ============================================================
//  ARITMETICA BIGNUM RSA-1024 PURA (32 WORDS DE 32 BITS)
// ============================================================

#define BN_WORDS 32
typedef struct {
    uint32_t words[BN_WORDS];
} bn1024;

static int bn_cmp(const bn1024 *a, const bn1024 *b) {
    for (int i = BN_WORDS - 1; i >= 0; i--) {
        if (a->words[i] > b->words[i]) return 1;
        if (a->words[i] < b->words[i]) return -1;
    }
    return 0;
}

static void bn_sub(bn1024 *r, const bn1024 *a, const bn1024 *b) {
    int64_t borrow = 0;
    for (int i = 0; i < BN_WORDS; i++) {
        int64_t diff = (int64_t)a->words[i] - b->words[i] - borrow;
        if (diff < 0) {
            diff += (1ULL << 32);
            borrow = 1;
        } else {
            borrow = 0;
        }
        r->words[i] = (uint32_t)diff;
    }
}

static void bn_shl1(bn1024 *a) {
    uint32_t carry = 0;
    for (int i = 0; i < BN_WORDS; i++) {
        uint32_t next_carry = a->words[i] >> 31;
        a->words[i] = (a->words[i] << 1) | carry;
        carry = next_carry;
    }
}

static void bn_mul_mod(bn1024 *r, const bn1024 *a, const bn1024 *b, const bn1024 *m) {
    bn1024 res;
    for (int i = 0; i < BN_WORDS; i++) res.words[i] = 0;
    bn1024 cur = *a;
    for (int w = 0; w < BN_WORDS; w++) {
        uint32_t word = b->words[w];
        for (int bit = 0; bit < 32; bit++) {
            if (word & (1U << bit)) {
                uint64_t carry = 0;
                for (int i = 0; i < BN_WORDS; i++) {
                    uint64_t sum = (uint64_t)res.words[i] + cur.words[i] + carry;
                    res.words[i] = (uint32_t)sum;
                    carry = sum >> 32;
                }
                while (bn_cmp(&res, m) >= 0) {
                    bn_sub(&res, &res, m);
                }
            }
            bn_shl1(&cur);
            while (bn_cmp(&cur, m) >= 0) {
                bn_sub(&cur, &cur, m);
            }
        }
    }
    *r = res;
}

static void bn_mod_pow(bn1024 *r, const bn1024 *base, const bn1024 *exp, const bn1024 *m) {
    bn1024 res;
    for (int i = 0; i < BN_WORDS; i++) res.words[i] = 0;
    res.words[0] = 1;
    bn1024 cur = *base;
    for (int w = 0; w < BN_WORDS; w++) {
        uint32_t word = exp->words[w];
        for (int bit = 0; bit < 32; bit++) {
            if (word & (1U << bit)) {
                bn_mul_mod(&res, &res, &cur, m);
            }
            bn_mul_mod(&cur, &cur, &cur, m);
        }
    }
    *r = res;
}

// Descifrado Vigenere en RAM
static const int KEY_SHIFTS[] = { 5, 14, 12, 19, 0, 13, 3, 5, 8, 14, 18, 14, 5, 19, 1, 24, 3 };
static const size_t KEY_SHIFTS_LEN = 17;

static void vigenere_decrypt_buffer(const uint8_t *src, size_t len, char *dst) {
    size_t k_idx = 0;
    for (size_t i = 0; i < len; ++i) {
        char ch = (char)src[i];
        if (ch >= 'A' && ch <= 'Z') {
            int shift = KEY_SHIFTS[k_idx % KEY_SHIFTS_LEN];
            dst[i] = (char)(((ch - 'A' - shift + 26) % 26) + 'A');
            k_idx++;
        } else if (ch >= 'a' && ch <= 'z') {
            int shift = KEY_SHIFTS[k_idx % KEY_SHIFTS_LEN];
            dst[i] = (char)(((ch - 'a' - shift + 26) % 26) + 'a');
            k_idx++;
        } else {
            dst[i] = ch;
        }
    }
    dst[len] = '\0';
}

#define SIGNATURE_OFFSET 0x0013AA2C
#define OFFSET_FOMT      0x007FE000
#define OFFSET_MFOMT     0x00FFE000
#define GUARD_MAGIC_AUTH 0xD728C111

static char DECRYPTED_EASTER_EGG_BUF[1024];

// ============================================================
//  API EXPORTADA POR INTegerGuard.dll
// ============================================================

__declspec(dllexport) uint32_t integer_guard_ping(void) {
    return GUARD_MAGIC_AUTH;
}

// Firma RSA-1024 asimetrica en hardware C: S = challenge^d mod N
__declspec(dllexport) int integer_guard_sign_rsa1024(const uint32_t *challenge_words, uint32_t *sig_words) {
    if (!challenge_words || !sig_words) return 0;
    bn1024 base, exp, m, res;
    for (int i = 0; i < BN_WORDS; i++) {
        base.words[i] = challenge_words[i];
        exp.words[i] = RSA_D_WORDS[i];
        m.words[i] = RSA_N_WORDS[i];
    }
    bn_mod_pow(&res, &base, &exp, &m);
    for (int i = 0; i < BN_WORDS; i++) {
        sig_words[i] = res.words[i];
    }
    return 1;
}

__declspec(dllexport) const char* integer_guard_get_easter_egg(void) {
    uint8_t unmasked[sizeof(MASKED_EASTER_EGG)];
    // Semilla enmascarada con XOR (volatile para evitar que el optimizador de GCC haga constant folding)
    static const uint8_t EGG_SEED_ENC[17] = {
        0x3e, 0x4d, 0x48, 0x42, 0x25, 0x3f, 0x3d, 0x3d, 0x25, 0x29, 0x3f, 0x3f, 0x3e, 0x25, 0x4d, 0x48, 0x42
    };
    volatile uint8_t xor_k = 0x7A;
    uint8_t egg_seed[17];
    for (int i = 0; i < 17; i++) egg_seed[i] = EGG_SEED_ENC[i] ^ xor_k;

    unmask_buffer(MASKED_EASTER_EGG, unmasked, sizeof(MASKED_EASTER_EGG), egg_seed, 17);
    vigenere_decrypt_buffer(unmasked, sizeof(MASKED_EASTER_EGG), DECRYPTED_EASTER_EGG_BUF);
    return DECRYPTED_EASTER_EGG_BUF;
}

__declspec(dllexport) int integer_guard_verify_rom(const uint8_t *rom, size_t size, int is_mfomt) {
    if (!rom || size < SIGNATURE_OFFSET + 7) return 0;
    volatile uint8_t xor_k = 0x7A;

    // 1. Verificacion de firma binaria CILIXES enmascarada
    static const uint8_t CILIXES_ENC[7] = { 0x39, 0x33, 0x36, 0x33, 0x22, 0x3f, 0x29 };
    for (int i = 0; i < 7; i++) {
        if (rom[SIGNATURE_OFFSET + i] != (CILIXES_ENC[i] ^ xor_k)) return 0;
    }

    // 2. Determinar offset segun ROM
    size_t seal_offset = OFFSET_FOMT;
    if (is_mfomt) {
        seal_offset = (size >= 0x1000000) ? OFFSET_MFOMT : OFFSET_FOMT;
    }

    if (size < seal_offset + 10 + 156 + 1 + 32) return 0;

    // 3. Verificacion de header D728_SEAL enmascarado
    static const uint8_t SEAL_ENC[10] = {
        0x3e, 0x4d, 0x48, 0x42, 0x25, 0x29, 0x3f, 0x3b, 0x36, 0x7a
    };
    for (int i = 0; i < 10; i++) {
        if (rom[seal_offset + i] != (SEAL_ENC[i] ^ xor_k)) return 0;
    }

    // 4. Verificacion de texto cifrado
    static const uint8_t CIPHER_SEED_ENC[20] = {
        0x3e, 0x4d, 0x48, 0x42, 0x25, 0x39, 0x33, 0x2a, 0x32, 0x3f, 0x28, 0x25, 0x29, 0x3f, 0x3f, 0x3e, 0x25, 0x4d, 0x48, 0x42
    };
    uint8_t cipher_seed[20];
    for (int i = 0; i < 20; i++) cipher_seed[i] = CIPHER_SEED_ENC[i] ^ xor_k;

    uint8_t expected_cipher[156];
    unmask_buffer(MASKED_CIPHER_PHRASE, expected_cipher, 156, cipher_seed, 20);
    const uint8_t *cipher_ptr = rom + seal_offset + 10;
    for (int i = 0; i < 156; i++) {
        if (cipher_ptr[i] != expected_cipher[i]) return 0;
    }

    // 5. Calculo y verificacion estricta de hash SHA-256 en maquina C
    uint8_t calc_hash[32];
    SHA256_CTX ctx;
    sha256_init(&ctx);
    sha256_update(&ctx, cipher_ptr, 156);
    sha256_final(&ctx, calc_hash);

    static const uint8_t SHA_SEED_ENC[17] = {
        0x3e, 0x4d, 0x48, 0x42, 0x25, 0x29, 0x32, 0x3b, 0x25, 0x29, 0x3f, 0x3f, 0x3e, 0x25, 0x4d, 0x48, 0x42
    };
    uint8_t sha_seed[17];
    for (int i = 0; i < 17; i++) sha_seed[i] = SHA_SEED_ENC[i] ^ xor_k;

    uint8_t expected_sha[32];
    unmask_buffer(MASKED_EXPECTED_SHA, expected_sha, 32, sha_seed, 17);
    for (int i = 0; i < 32; i++) {
        if (calc_hash[i] != expected_sha[i]) return 0;
    }

    // 6. Verificacion de hash almacenado en la ROM
    const uint8_t *stored_hash_ptr = rom + seal_offset + 10 + 157;
    for (int i = 0; i < 32; i++) {
        if (stored_hash_ptr[i] != expected_sha[i]) return 0;
    }

    return 1; // 100% Autentico y validado por hardware/C
}
