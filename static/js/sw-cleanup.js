(function() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.getRegistrations().then(function(registrations) {
      if (registrations.length) {
        Promise.all(registrations.map(function(reg) { return reg.unregister(); })).then(function() {
          if (caches) {
            caches.keys().then(function(names) {
              Promise.all(names.map(function(n) { return caches.delete(n); })).then(function() {
                location.reload(true);
              });
            });
          }
        });
      }
    });
  }
})();
