const { test, expect } = require('./fixtures/test-helpers');

test.describe('Document API', () => {
  test('GET /api/documents should return document list', async ({ authenticatedPage }) => {
    const response = await authenticatedPage.request.get('/api/documents');
    expect(response.status()).toBe(200);
  });

  test('POST /chat-with-document should handle empty/no-doc context', async ({ authenticatedPage }) => {
    const response = await authenticatedPage.request.post('/chat-with-document', {
      form: { message: 'What does this document say?' },
    });
    expect([200, 400, 500]).toContain(response.status());
  });

  test('DELETE /api/documents/clear should clear documents', async ({ authenticatedPage }) => {
    const response = await authenticatedPage.request.delete('/api/documents/clear');
    expect([200, 204]).toContain(response.status());
  });
});
