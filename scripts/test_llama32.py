from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

model_name = "meta-llama/Llama-3.2-1B-Instruct"

print("🔹 모델 로딩 중... (처음 한 번은 시간이 걸립니다)")
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.float32,   # CPU 강제
    device_map="cpu"
)

prompt = "번역: Hello, how are you?"
inputs = tokenizer(prompt, return_tensors="pt")
outputs = model.generate(**inputs, max_new_tokens=50)
print("✅ 결과:\n", tokenizer.decode(outputs[0], skip_special_tokens=True))