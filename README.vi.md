# Lily MCP

[English](README.md)

Integration cho Home Assistant giúp trợ lý giọng nói [Xiaozhi](https://xiaozhi.me) (ví dụ Lily Box)
điều khiển nhà qua **MCP endpoint** của agent.

Thay vì đưa cho agent cả bộ công cụ Assist của Home Assistant, integration chỉ đưa 5 công cụ đơn giản
cho những thiết bị bạn chọn:

| Công cụ | Việc làm |
|---|---|
| `list_devices` | Liệt kê các thiết bị đã chọn và trạng thái hiện tại |
| `turn_on` | Bật thiết bị (robot hút bụi: bắt đầu dọn, rèm: mở) |
| `turn_off` | Tắt thiết bị (robot hút bụi: về dock, rèm: đóng) |
| `get_state` | Xem trạng thái một thiết bị hoặc cảm biến |
| `set_temperature` | Đặt nhiệt độ điều hoà (chỉ có khi bạn chọn điều hoà) |

Tham số `name` là danh sách cố định các tên thiết bị, nên model nhỏ cũng chọn đúng. Tên được so khớp
không phân biệt dấu tiếng Việt, alias của entity cũng dùng được.

Không cần thư viện pip. Home Assistant tự mở kết nối WebSocket tới Xiaozhi, nên không cần mở cổng ra
Internet.

## Cài đặt

1. HACS → ⋮ → *Custom repositories* → thêm `https://github.com/lipnguyen-ha/ha-lily-mcp`, loại
   **Integration**.
2. Tải **Lily MCP**, rồi khởi động lại Home Assistant.

Cài tay: copy `custom_components/lily_mcp/` vào `<config>/custom_components/lily_mcp/`.

## Cấu hình

1. Trên xiaozhi.me mở agent → *Configure* → *Extensions* → *MCP Endpoint*, copy địa chỉ
   (`wss://api.xiaozhi.me/mcp/?token=...`). Giữ kín: ai có địa chỉ này là điều khiển được thiết bị của bạn.
2. *Settings → Devices & services → Add integration → Lily MCP*. Dán endpoint và chọn thiết bị.
3. Refresh trang MCP Endpoint trên xiaozhi.me: trạng thái chuyển *Online* và hiện danh sách công cụ.
4. Khởi động lại thiết bị Xiaozhi để phiên trò chuyện mới nhận công cụ.

Muốn đổi thiết bị hoặc endpoint thì bấm *Configure* trên integration, nó sẽ kết nối lại với danh sách
công cụ mới.

Nếu có integration khác (ví dụ *MCP Server for Xiaozhi*) cũng nối vào cùng endpoint, hãy disable nó để
agent chỉ thấy một bộ công cụ.

## Gỡ lỗi

```yaml
logger:
  logs:
    custom_components.lily_mcp: debug
```

Mỗi lần gọi công cụ được ghi ở mức `info` dạng `Tool call <tên> <tham số>`. Ở mức `debug` thì mọi tin
JSON-RPC vào ra cũng được ghi lại.

## Giấy phép

MIT
