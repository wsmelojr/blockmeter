from ecdsa import SigningKey

if __name__ == "__main__":
    sk = SigningKey.generate() # uses NIST192p
    vk = sk.verifying_key
    signature = sk.sign(b"message")

    print(signature)

    assert vk.verify(signature, b"message")