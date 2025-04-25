import urllib.parse

# Function to encode a URL
def encode_url(url: str) -> str:
    return urllib.parse.quote(url)

# Test function to demonstrate encoding
def test_url_encoding():
    url = "https://example.com/path/to file with spaces"
    encoded_url = encode_url(url)
    print(f"Original URL: {url}")
    print(f"Encoded URL: {encoded_url}")

# Run the test
if __name__ == "__main__":
    test_url_encoding()
