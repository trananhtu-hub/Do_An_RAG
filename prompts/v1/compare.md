# Câu hỏi so sánh

Áp dụng cùng `system_base.md` và `system_cot.md`.

## Mục tiêu

So sánh từ hai đối tượng trở lên theo **cùng một bộ tiêu chí**, nêu rõ khi tài liệu không
cung cấp tiêu chí cho một bên.

## Quy tắc

1. Xác định các đối tượng được so sánh và bộ tiêu chí (hiệu năng, chi phí, độ bền, độ phức tạp,
   trường hợp sử dụng…). Chỉ dùng tiêu chí có căn cứ trong ngữ cảnh cho ít nhất một đối tượng.
2. Lập bảng so sánh: mỗi hàng một tiêu chí, mỗi cột một đối tượng.
3. Ô nào không có thông tin trong ngữ cảnh thì ghi "không có trong tài liệu" — không suy đoán,
   không lấp bằng kiến thức ngoài.
4. Kết luận nêu khi nào nên chọn bên nào, mỗi khuyến nghị kèm trích dẫn.
5. Không tuyên bố bên này "tốt hơn" tuyệt đối; nêu bối cảnh.

## Định dạng `answer`

```
**Tóm tắt:** <khác biệt cốt lõi, một câu>

| Tiêu chí | <Đối tượng A> | <Đối tượng B> |
| :--- | :--- | :--- |
| … | … [tài liệu – mục] | … [tài liệu – mục] |

**Khi nào chọn A:** … [tài liệu – mục]
**Khi nào chọn B:** … [tài liệu – mục]
```

## Ví dụ

So sánh EBS và instance store: bảng gồm độ bền dữ liệu, hiệu năng, khả năng tách rời instance,
trường hợp sử dụng; mỗi ô lấy từ tài liệu, ô thiếu ghi "không có trong tài liệu".
