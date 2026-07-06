# Maintainer: Adrin Jalali <adrin.jalali@gmail.com>
pkgname=aur-cooldown
pkgver=0.5.0
pkgrel=1
pkgdesc="Age-delay AUR upgrades so malicious or broken pushes are caught before they land"
arch=('any')
url="https://github.com/adrinjalali/aur-cooldown"
license=('MIT')
depends=('python' 'git' 'yay')
source=("$pkgname-$pkgver.tar.gz::$url/archive/refs/tags/v$pkgver.tar.gz")
sha256sums=('SKIP')  # replace with the real checksum on release

package() {
  cd "$pkgname-$pkgver"
  make PREFIX=/usr DESTDIR="$pkgdir" install
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
}
