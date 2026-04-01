declare module '@barba/core' {
  // Barba doesn't ship types; we keep this local shim tiny on purpose.
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const barba: any
  export default barba
}

