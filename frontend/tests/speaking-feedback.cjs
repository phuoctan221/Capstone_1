const { buildSync } = require("esbuild");
const path = require("node:path");

global.window = {};
const source = `
import React from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import assert from 'node:assert/strict';
import Feedback from './src/components/SpeakingFeedback.jsx';
const render = result => renderToStaticMarkup(React.createElement(Feedback, { result }));
const invoice = { word: 'invoice', quality_score: null, phone_score_list:
  ['ih', 'n', 'v', 'oy', 's'].map(phone => ({phone, recognized_phone: phone, quality_score: null})) };
const html = render({status: 'scored', words: [invoice]});
assert(html.includes('Các âm đã khớp'));
assert(html.includes('/ɪ/'));
assert(html.includes('/ɔɪ/'));
assert.equal((html.match(/class="good"/g) || []).length, 5);
assert(!html.includes('0/100'));
assert(!html.includes('Chưa có đủ nhận xét'));
const mismatch = render({words: [{word: 'very', phone_score_list: [{phone: 'v', recognized_phone: 'w', quality_score: null}]}]});
assert(mismatch.includes('nghe gần /w/'));
assert(mismatch.includes('Ưu tiên luyện: /v/'));
assert(mismatch.includes('needs-practice'));
const unknown = render({words: [{word: 'very', phone_score_list: [{phone: 'v', quality_score: null}]}]});
assert(unknown.includes('Chưa nghe rõ âm này'));
assert(!unknown.includes('class="good"'));
const scored = render({words: [{word: 'very', phone_score_list: [{phone: 'v', quality_score: 40}]}]});
assert(scored.includes('40/100'));
assert(scored.includes('needs-practice'));
const retry = render({status: 'retry', words: [invoice]});
assert(!retry.includes('Đã đọc khớp'));
assert(retry.includes('Cách luyện lại'));
console.log('Passed: invoice without numeric scores, differing sounds, unknown sounds, numeric scores, retry.');
`;
const output = buildSync({
  stdin: { contents: source, resolveDir: path.resolve(__dirname, ".."), loader: "jsx" },
  jsx: "automatic", bundle: true, platform: "node", format: "cjs", write: false,
});
new Function("require", output.outputFiles[0].text)(require);
