from backend.app.services.ocr_extractor import TrOCRExtractor

print('Initializing OCR (this may load model)...')
ocr = TrOCRExtractor()

# Blank image (all zeros) should produce empty/low-confidence and trigger retries
class FakeImageBlank:
    def convert(self, mode=None):
        return self
    def getextrema(self):
        return (255, 255)

class FakeImageNoisy:
    def convert(self, mode=None):
        return self
    def getextrema(self):
        return (0, 255)

blank = FakeImageBlank()
res_blank = ocr.extract_text(blank)
print('\n--- Blank image result ---')
print(res_blank)

noisy = FakeImageNoisy()
res_noisy = ocr.extract_text(noisy)
print('\n--- Noisy image result ---')
print(res_noisy)
