import { afterEach, describe, expect, it, vi } from 'vitest';
import { api } from './client';
afterEach(() => vi.unstubAllGlobals());
describe('API errors and payloads', () => {
  it('handles FastAPI validation errors without a business error code', async () => {
    vi.stubGlobal(
      'fetch',
      vi
        .fn()
        .mockResolvedValue(
          new Response(JSON.stringify({ detail: [{ msg: 'Field required' }] }), { status: 422 }),
        ),
    );
    await expect(api.round1('S001', [], 0)).rejects.toMatchObject({
      code: 'HTTP_422',
      message: expect.stringContaining('校验'),
      detail: expect.stringContaining('Field required'),
    });
  });
  it('sends exactly one section for second-round enrollment', async () => {
    const fetch = vi.fn().mockResolvedValue(new Response('{"ok":true}'));
    vi.stubGlobal('fetch', fetch);
    await api.round2('S001', 'ART_A');
    expect(JSON.parse(fetch.mock.calls[0][1].body)).toEqual({ student_id: 'S001', section_id: 'ART_A' });
  });
  it('surfaces business failures, offline failures and invalid server responses', async () => {
    const fetch = vi
      .fn()
      .mockResolvedValueOnce(new Response('{"code":"NO_SEAT","message":"No seats"}', { status: 409 }))
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
      .mockResolvedValueOnce(new Response('<html>proxy unavailable</html>'));
    vi.stubGlobal('fetch', fetch);
    await expect(api.round2('S001', 'ART_A')).rejects.toMatchObject({ code: 'NO_SEAT' });
    await expect(api.state('S001')).rejects.toMatchObject({ code: 'NETWORK' });
    await expect(api.catalog()).rejects.toMatchObject({ code: 'BAD_RESPONSE' });
  });
});
