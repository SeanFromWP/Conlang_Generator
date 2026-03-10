import random

class WordGenerator:
    def __init__(self, phonology_config):

        self.config = phonology_config
        self.consonants = phonology_config.get('inventory_consonants', [])
        self.vowels = phonology_config.get('inventory_vowels', [])
        self.weights = phonology_config.get('weights', {})
        
        # 提取權重清單，若無則預設為 10
        self.c_weights = [self.weights.get('consonants', {}).get(c, 10) for c in self.consonants]
        self.v_weights = [self.weights.get('vowels', {}).get(v, 10) for v in self.vowels]

    def _generate_syllable(self, pattern="CVC"):
        syllable = ""

        for char in pattern:
            if char == 'C' and self.consonants:
                syllable += random.choices(self.consonants, weights=self.c_weights, k=1)[0]
            elif char == 'V' and self.vowels:
                syllable += random.choices(self.vowels, weights=self.v_weights, k=1)[0]

        return syllable

    def generate(self, count=10, pattern="CVC", min_syl=1, max_syl=3, translations=None):
        results = []
        for i in range(count):
            num_syl = random.randint(min_syl, max_syl)
            word_ipa = "".join([self._generate_syllable(pattern) for _ in range(num_syl)])
            
            # 判斷是否有對應的翻譯詞
            current_trans = translations[i] if (translations and i < len(translations)) else "???"
            
            results.append({
                "word": word_ipa,
                "translation": current_trans,
                "pos": "noun"  # 這裡你之後可以進階做詞性自動判斷
            })

        return results

# 接口更新
def func(count, config, pattern, min_syl, max_syl, translations=None):
    gen = WordGenerator(config)
    return gen.generate(count, pattern, min_syl, max_syl, translations)