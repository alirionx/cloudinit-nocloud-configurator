import { describe, expect, it } from 'vitest'
import { maskSecrets } from './components/secrets'
import { languageForPath } from './components/languages'
import { mergeTags, moveItem, randomSuffix, suggestInstanceId } from './form'

describe('FR-005: instance-id suggestion', () => {
  it('uses iid-<hostname>-<suffix>', () => {
    expect(suggestInstanceId('web-01', 'abcd1234')).toBe('iid-web-01-abcd1234')
  })
  it('falls back to iid-<suffix> without a valid hostname', () => {
    expect(suggestInstanceId(null, 'abcd1234')).toBe('iid-abcd1234')
    expect(suggestInstanceId('bad host', 'abcd1234')).toBe('iid-abcd1234')
  })
  it('generates 8 hex characters', () => {
    expect(randomSuffix()).toMatch(/^[0-9a-f]{8}$/)
  })
})

describe('FR-007: tag input', () => {
  it('splits "git, wget docker.io" into three entries', () => {
    expect(mergeTags([], 'git, wget docker.io')).toEqual(['git', 'wget', 'docker.io'])
  })
  it('does not add an entry twice', () => {
    expect(mergeTags(['git'], 'git wget git')).toEqual(['git', 'wget'])
  })
  it('splits pasted multi-line lists', () => {
    expect(mergeTags([], 'curl\nvim\n\n jq ')).toEqual(['curl', 'vim', 'jq'])
  })
  it('keeps spaces inside entries when only Enter separates', () => {
    expect(mergeTags(['echo'], 'hello world', /\n+/)).toEqual(['echo', 'hello world'])
  })
})

describe('FR-009: reordering', () => {
  it('moves entries', () => {
    const list = ['a', 'b', 'c']
    moveItem(list, 0, 2)
    expect(list).toEqual(['b', 'c', 'a'])
    moveItem(list, 2, 5)
    expect(list).toEqual(['b', 'c', 'a'])
  })
})

describe('FR-013: secrets masking', () => {
  it('masks crypt hashes', () => {
    const text = 'passwd: $6$salt$' + 'a'.repeat(86) + '\nname: x\n'
    expect(maskSecrets(text)).toBe('passwd: ********\nname: x\n')
  })
  it('masks quoted yescrypt hashes', () => {
    expect(maskSecrets("passwd: '$y$j9T$abc$def'")).toBe("passwd: '********'")
  })
  it('leaves other text alone', () => {
    expect(maskSecrets('price: $5 and $HOME')).toBe('price: $5 and $HOME')
  })
})

describe('FR-008: syntax highlighting by file extension', () => {
  it.each([
    ['/opt/setup.sh', 'shell'],
    ['/etc/app/config.yaml', 'yaml'],
    ['/etc/app/config.YML', 'yaml'],
    ['/etc/app/settings.json', 'json'],
    ['/etc/nginx/nginx.conf', 'properties'],
    ['/etc/systemd/system/app.service', 'properties'],
    ['/etc/motd', 'text'],
  ])('%s -> %s', (path, language) => {
    expect(languageForPath(path)).toBe(language)
  })
})
